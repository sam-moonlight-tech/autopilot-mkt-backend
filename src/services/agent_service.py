"""Agent service for OpenAI-powered conversations."""

import asyncio
import json
import logging
import time
from typing import Any
from uuid import UUID

from openai import OpenAIError

from src.core.config import get_settings
from src.core.openai import get_openai_client
from src.core.token_budget import TokenBudgetError, get_token_budget
from src.models.conversation import ConversationPhase
from src.models.message import MessageRole
from src.schemas.message import MessageResponse
from src.services.conversation_service import ConversationService
from src.services.extraction_constants import REQUIRED_QUESTIONS, REQUIRED_QUESTION_KEYS
from src.services.rag_service import RAGService, get_rag_service
from src.services.robot_catalog_service import RobotCatalogService
from src.services.sales_knowledge_service import SalesKnowledgeService, get_sales_knowledge_service
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)

# Cache for sales knowledge per conversation+phase (maxsize limits memory usage)
# Key: (conversation_id, phase) -> sales_knowledge_text
_sales_knowledge_cache: dict[tuple[str, str], str] = {}
_SALES_KNOWLEDGE_CACHE_MAX_SIZE = 1000  # Limit cache to prevent memory bloat


def clear_sales_knowledge_cache(conversation_id: UUID | None = None) -> int:
    """Clear sales knowledge cache entries.

    Args:
        conversation_id: If provided, only clear entries for this conversation.
                        If None, clear all entries.

    Returns:
        int: Number of entries cleared.
    """
    global _sales_knowledge_cache

    if conversation_id is None:
        count = len(_sales_knowledge_cache)
        _sales_knowledge_cache.clear()
        return count

    conv_str = str(conversation_id)
    keys_to_remove = [k for k in _sales_knowledge_cache if k[0] == conv_str]
    for key in keys_to_remove:
        del _sales_knowledge_cache[key]
    return len(keys_to_remove)

# System prompts for each conversation phase
SYSTEM_PROMPTS: dict[ConversationPhase, str] = {
    ConversationPhase.DISCOVERY: """You are Autopilot, an expert robotics procurement consultant helping companies discover their automation needs.

Your role in the Discovery phase:
- Ask thoughtful questions to understand the user's current operations
- Identify pain points and areas where robotics could help
- Gather information about their industry, scale, and specific challenges
- Be curious, professional, and supportive

Guidelines:
- Ask one or two questions at a time, don't overwhelm
- Summarize what you've learned periodically
- When you have a good understanding, suggest moving to ROI analysis
- Stay focused on understanding their needs before recommending solutions""",
    ConversationPhase.ROI: """You are Autopilot, an expert robotics procurement consultant helping companies analyze ROI for automation.

Your role in the ROI phase:
- Help quantify current costs (labor, errors, throughput)
- Estimate potential savings from automation
- Discuss implementation costs and timelines
- Calculate payback periods and ROI projections

Guidelines:
- Use concrete numbers when possible
- Ask for specifics to make calculations accurate
- Present projections clearly with assumptions stated
- When ROI is established, suggest moving to product selection""",
    ConversationPhase.GREENLIGHT: """You are Autopilot, an expert robotics procurement consultant helping companies finalize their robotics selections and move to checkout.

Your role in the Greenlight phase:
- Help users finalize their product selections
- Answer questions about pricing, leasing options, and subscriptions
- Guide them through the checkout process
- Discuss implementation timelines and next steps

Guidelines:
- Base recommendations on information gathered in discovery and ROI analysis
- Be clear about pricing - we offer monthly lease subscriptions
- Help compare selected robots and confirm their choices
- Provide robot recommendations from our catalog when asked
- Encourage them to proceed to checkout when ready
- Be supportive of their decision-making process""",
}

# JSON Schema for structured discovery responses with chips
DISCOVERY_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "discovery_response",
        "schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Agent's conversational response"
                },
                "chips": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quick reply options for the user (empty array for text inputs)"
                },
                "ready_for_roi": {
                    "type": "boolean",
                    "description": "True when enough info gathered to show ROI analysis"
                }
            },
            "required": ["content", "chips", "ready_for_roi"],
            "additionalProperties": False
        },
        "strict": True
    }
}


class AgentService:
    """Service for AI agent interactions."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        sales_knowledge_service: SalesKnowledgeService | None = None,
        session_service: SessionService | None = None,
    ) -> None:
        """Initialize agent service.

        Args:
            rag_service: Optional RAG service for testing.
            sales_knowledge_service: Optional sales knowledge service for testing.
            session_service: Optional session service for testing.
        """
        self.client = get_openai_client()
        self.settings = get_settings()
        self.conversation_service = ConversationService()
        self.session_service = session_service or SessionService()
        self._rag_service = rag_service
        self._sales_knowledge_service = sales_knowledge_service

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    @property
    def sales_knowledge_service(self) -> SalesKnowledgeService:
        """Get sales knowledge service."""
        if self._sales_knowledge_service is None:
            self._sales_knowledge_service = get_sales_knowledge_service()
        return self._sales_knowledge_service

    def _get_cached_sales_knowledge(
        self, conversation_id: UUID, phase: ConversationPhase
    ) -> str:
        """Get sales knowledge for a conversation, caching per conversation+phase.

        This optimization reduces token usage by ~400-600 tokens per message
        by reusing the same sales knowledge throughout a conversation phase
        instead of randomly selecting new snippets each time.

        Args:
            conversation_id: The conversation's UUID.
            phase: Current conversation phase.

        Returns:
            str: Cached sales knowledge context.
        """
        global _sales_knowledge_cache

        cache_key = (str(conversation_id), phase.value)

        # Return cached value if available
        if cache_key in _sales_knowledge_cache:
            logger.debug("Using cached sales knowledge for %s/%s", conversation_id, phase.value)
            return _sales_knowledge_cache[cache_key]

        # Generate new sales knowledge
        try:
            if phase == ConversationPhase.DISCOVERY:
                sales_knowledge = self.sales_knowledge_service.get_discovery_context()
            elif phase == ConversationPhase.ROI:
                sales_knowledge = self.sales_knowledge_service.get_roi_context()
            elif phase == ConversationPhase.GREENLIGHT:
                sales_knowledge = self.sales_knowledge_service.get_greenlight_context()
            else:
                sales_knowledge = ""
        except Exception as e:
            logger.warning("Failed to load sales knowledge: %s", e)
            sales_knowledge = ""

        # Evict oldest entries if cache is full (simple FIFO eviction)
        if len(_sales_knowledge_cache) >= _SALES_KNOWLEDGE_CACHE_MAX_SIZE:
            # Remove first 100 entries to make room
            keys_to_remove = list(_sales_knowledge_cache.keys())[:100]
            for key in keys_to_remove:
                del _sales_knowledge_cache[key]
            logger.debug("Evicted %d entries from sales knowledge cache", len(keys_to_remove))

        # Cache the result
        _sales_knowledge_cache[cache_key] = sales_knowledge
        logger.debug("Cached sales knowledge for %s/%s", conversation_id, phase.value)

        return sales_knowledge

    def get_system_prompt(self, phase: ConversationPhase) -> str:
        """Get the system prompt for a conversation phase.

        Args:
            phase: The current conversation phase.

        Returns:
            str: The system prompt for the phase.
        """
        return SYSTEM_PROMPTS.get(phase, SYSTEM_PROMPTS[ConversationPhase.DISCOVERY])

    def _get_mock_response(self, phase: ConversationPhase, user_message: str) -> str:
        """Generate a mock response for testing without consuming API tokens.

        Args:
            phase: The current conversation phase.
            user_message: The user's message.

        Returns:
            str: A mock response appropriate for the phase.
        """
        mock_responses = {
            ConversationPhase.DISCOVERY: (
                "[MOCK] Thanks for sharing that! I'd love to learn more about your operations. "
                "What types of tasks are currently taking up most of your team's time? "
                "And roughly how many employees are involved in these processes?"
            ),
            ConversationPhase.ROI: (
                "[MOCK] Based on what you've shared, let me help quantify the potential ROI. "
                "If you're spending around $50/hour on labor for these tasks, and automation "
                "could reduce that by 60%, you'd be looking at significant monthly savings. "
                "What's your current monthly spend on these manual processes?"
            ),
            ConversationPhase.GREENLIGHT: (
                "[MOCK] Great choice! Based on your requirements, I'd recommend looking at "
                "our collaborative robot solutions. They start at around $2,500/month on a "
                "lease basis. Would you like me to add this to your cart so you can review "
                "the full details?"
            ),
        }
        return mock_responses.get(phase, mock_responses[ConversationPhase.DISCOVERY])

    async def build_context(
        self,
        conversation_id: UUID,
        phase: ConversationPhase,
        current_message: str | None = None,
    ) -> list[dict[str, str]]:
        """Build the message context for OpenAI API.

        Args:
            conversation_id: The conversation's UUID.
            phase: Current conversation phase.
            current_message: Optional current user message for RAG context.

        Returns:
            list[dict]: List of message dicts for OpenAI API.
        """
        # Start with system prompt
        system_prompt = self.get_system_prompt(phase)

        # Add RAG context for greenlight phase or when user asks about products
        if current_message and phase in (
            ConversationPhase.GREENLIGHT,
            ConversationPhase.ROI,
        ):
            product_context = await self.rag_service.get_relevant_products_for_context(
                query=current_message,
                top_k=5,
            )
            if product_context:
                system_prompt += f"\n\n{product_context}"

        # Add phase-specific sales knowledge from real customer conversations
        # Uses caching to reduce token usage (~400-600 tokens saved per message)
        sales_knowledge = self._get_cached_sales_knowledge(conversation_id, phase)
        if sales_knowledge:
            system_prompt += f"\n\n{sales_knowledge}"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Get recent conversation history
        recent_messages = await self.conversation_service.get_recent_messages(
            conversation_id, limit=self.settings.max_context_messages
        )

        # Add conversation history
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        return messages

    async def generate_response(
        self,
        conversation_id: UUID,
        user_message: str,
        metadata: dict[str, Any] | None = None,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
    ) -> tuple[MessageResponse, MessageResponse]:
        """Generate an agent response to a user message.

        Stores both the user message and agent response.

        Args:
            conversation_id: The conversation's UUID.
            user_message: The user's message content.
            metadata: Optional metadata for the user message.
            session_id: Optional session ID for token budget tracking (anonymous).
            profile_id: Optional profile ID for token budget tracking (authenticated).

        Returns:
            tuple: (user_message_response, agent_message_response)

        Raises:
            TokenBudgetError: If daily token budget is exceeded.
            Exception: If OpenAI API call fails.
        """
        # Get conversation to determine phase
        conversation = await self.conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        phase = ConversationPhase(conversation["phase"])

        # Store user message first
        user_msg_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_message,
            metadata=metadata,
        )

        user_msg_response = MessageResponse(
            id=user_msg_data["id"],
            conversation_id=user_msg_data["conversation_id"],
            role=user_msg_data["role"],
            content=user_msg_data["content"],
            metadata=user_msg_data.get("metadata", {}),
            created_at=user_msg_data["created_at"],
        )

        # Build context including the new user message and RAG context
        context = await self.build_context(conversation_id, phase, user_message)

        # Determine budget key and check token budget
        budget_key: str | None = None
        is_authenticated = False
        if profile_id:
            budget_key = f"user:{profile_id}"
            is_authenticated = True
        elif session_id:
            budget_key = f"session:{session_id}"

        # Check if mock mode is enabled
        if self.settings.mock_openai:
            logger.info("Mock mode enabled - returning mock response")
            agent_content = self._get_mock_response(phase, user_message)
        else:
            # Check token budget before making API call
            if budget_key:
                token_budget = get_token_budget()
                # Estimate tokens: rough estimate of input + max output
                estimated_tokens = len(user_message) // 4 + 1000  # ~4 chars per token
                allowed, remaining, limit = await token_budget.check_budget(
                    budget_key, estimated_tokens, is_authenticated
                )
                if not allowed:
                    raise TokenBudgetError(
                        message="Daily token budget exceeded. Please try again tomorrow.",
                        tokens_used=limit - remaining,
                        daily_limit=limit,
                    )

            try:
                # Call OpenAI API
                response = self.client.chat.create(
                    model=self.settings.openai_model,
                    messages=context,  # type: ignore[arg-type]
                    max_completion_tokens=1000,
                    temperature=0.7,
                )

                agent_content = response.choices[0].message.content or ""

                # Track actual token usage
                if budget_key and response.usage:
                    total_tokens = response.usage.total_tokens
                    await token_budget.record_usage(budget_key, total_tokens)
                    logger.debug(
                        "Token usage recorded: %d tokens for %s",
                        total_tokens,
                        budget_key,
                    )

            except OpenAIError as e:
                logger.error("OpenAI API error: %s", str(e))
                agent_content = (
                    "I apologize, but I'm having trouble processing your request right now. "
                    "Please try again in a moment."
                )

        # Store agent response
        agent_msg_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=agent_content,
            metadata={"model": self.settings.openai_model},
        )

        agent_msg_response = MessageResponse(
            id=agent_msg_data["id"],
            conversation_id=agent_msg_data["conversation_id"],
            role=agent_msg_data["role"],
            content=agent_msg_data["content"],
            metadata=agent_msg_data.get("metadata", {}),
            created_at=agent_msg_data["created_at"],
        )

        return user_msg_response, agent_msg_response

    def _format_recommendations_context(
        self,
        recommendations: Any,
    ) -> str:
        """Format current recommendations for agent context.

        Args:
            recommendations: RecommendationsResponse or None.

        Returns:
            str: Formatted recommendations context for prompt.
        """
        if not recommendations or not hasattr(recommendations, 'recommendations'):
            return ""

        recs = recommendations.recommendations
        if not recs:
            return ""

        lines = ["\nCURRENT ROBOT RECOMMENDATIONS FOR THIS CUSTOMER:"]
        for rec in recs[:3]:  # Top 3 recommendations
            lines.append(
                f"- #{rec.rank} {rec.robot_name} (Score: {rec.match_score}/100, Label: {rec.label})"
            )
            lines.append(f"  Why: {rec.summary}")
            for reason in rec.reasons[:2]:  # Top 2 reasons
                lines.append(f"  • {reason.factor}: {reason.explanation}")

        lines.append("")
        lines.append("When the user asks about recommendations, reference this analysis.")
        lines.append("Explain the scoring factors and why specific robots match their needs.")

        return "\n".join(lines)

    def _build_discovery_prompt(
        self,
        current_answers: dict[str, Any],
        missing_questions: list[dict[str, Any]],
        robot_catalog: list[dict[str, Any]],
        current_recommendations: Any = None,
        current_user_message: str | None = None,
    ) -> str:
        """Build an intelligent discovery system prompt.

        The prompt tells the agent what's already known, what still needs
        to be gathered, what robots are available, and current recommendations.

        Args:
            current_answers: Dict of already answered questions.
            missing_questions: List of required questions not yet answered.
            robot_catalog: List of available robots in the catalog.
            current_recommendations: Optional RecommendationsResponse with current recs.
            current_user_message: The user's current message (to recognize inline answers).

        Returns:
            str: The system prompt for discovery.
        """
        # Format what we already know
        if current_answers:
            answered_summary = "\n".join(
                f"- {key}: {ans.get('value', 'unknown')}"
                for key, ans in current_answers.items()
            )
        else:
            answered_summary = "None yet - this is a new conversation."

        # Format what we still need to learn
        if missing_questions:
            missing_summary = "\n".join(
                f"- {q['key']}: \"{q['question']}\" (chips: {q['chips'] or 'free text'})"
                for q in missing_questions[:3]  # Show top 3 priorities
            )
            remaining_count = len(missing_questions)
        else:
            missing_summary = "All required questions answered!"
            remaining_count = 0

        # Format the robot catalog
        if robot_catalog:
            catalog_summary = "\n".join(
                f"- **{r.get('name', 'Unknown')}**: {r.get('category', 'Robot')} | "
                f"Best for: {r.get('best_for', 'general use')} | "
                f"Modes: {', '.join(r.get('modes', []))} | "
                f"Monthly lease: ${r.get('monthly_lease', 0):,.0f}"
                for r in robot_catalog
            )
        else:
            catalog_summary = "No robots available in catalog."

        # Format recommendations if available
        recommendations_context = self._format_recommendations_context(current_recommendations)

        # Include current message for inline answer recognition
        current_message_context = ""
        if current_user_message:
            current_message_context = f"""
USER'S CURRENT MESSAGE (analyze for answers to missing questions):
"{current_user_message}"

CRITICAL: Before asking ANY question, check if the user's current message above ALREADY contains the answer.
For example, if user says "We're Pickleball One, a pickleball club" - they've answered BOTH company_name AND company_type.
Do NOT ask about information the user just provided. Acknowledge what they shared and move to the NEXT missing topic.
"""

        return f"""You are Autopilot, a premium robotics procurement consultant.

AVAILABLE ROBOT CATALOG (ONLY recommend from this list):
{catalog_summary}

WHAT YOU KNOW ABOUT THIS CUSTOMER (from previous messages):
{answered_summary}
{current_message_context}
STILL NEED TO LEARN ({remaining_count} remaining):
{missing_summary}
{recommendations_context}
INSTRUCTIONS:
1. FIRST, extract any new information from the user's current message - acknowledge what they shared
2. If there are STILL missing questions after considering the current message, weave ONE into your response
3. NEVER ask about something the user just told you in this message - move to the next unknown topic
4. Set ready_for_roi=true ONLY when you have answers for most required questions (4+ of 6)
5. Return chips matching the question you're asking, or empty array for open-ended questions
6. When discussing specific robots, ONLY mention robots from the AVAILABLE ROBOT CATALOG above
7. NEVER make up or hallucinate robot models - if asked about specific models, only reference the catalog
8. If recommendations are available, reference them when discussing robot options

TONE: Premium, consultative, efficient. Like a senior consultant who values the client's time.
Don't be robotic or interrogative. If user gives rich context, adapt and skip redundant questions.

IMPORTANT: Your response must be valid JSON with content (string), chips (array), and ready_for_roi (boolean)."""

    async def generate_initial_greeting(
        self,
        conversation_id: UUID,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
        source_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a dynamic initial greeting for a new conversation.

        This method generates a contextual greeting based on what we know about
        the user (discovery profile, company, referral source, etc.).

        Args:
            conversation_id: The conversation's UUID.
            session_id: Optional session ID for anonymous users.
            profile_id: Optional profile ID for authenticated users.
            source_context: Optional context about how user arrived (email, referral, etc.)

        Returns:
            dict: {
                "content": str,  # The greeting message
                "chips": list[str],  # Quick reply options
                "message": MessageResponse,  # The saved message
            }
        """
        # Gather context about what we know
        current_answers: dict[str, Any] = {}
        company_name: str | None = None
        discovery_service = None

        if profile_id:
            from src.services.discovery_profile_service import DiscoveryProfileService
            from src.services.company_service import CompanyService

            discovery_service = DiscoveryProfileService()
            discovery_profile = await discovery_service.get_by_profile_id(profile_id)
            if discovery_profile:
                current_answers = discovery_profile.get("answers", {})

            # Check for company
            company_service = CompanyService()
            company = await company_service.get_user_company(profile_id)
            if company and company.get("name"):
                company_name = company["name"]
                if "company_name" not in current_answers:
                    current_answers["company_name"] = {
                        "questionId": 0,
                        "value": company_name,
                        "label": "Company Name",
                        "key": "company_name",
                        "group": "Company",
                    }
        elif session_id:
            session = await self.session_service.get_session_by_id(session_id)
            if session:
                current_answers = session.get("answers", {})
                if "company_name" in current_answers:
                    company_name = current_answers["company_name"].get("value")

        # Determine what's missing
        answered_keys = set(current_answers.keys())
        missing_questions = [
            q for q in REQUIRED_QUESTIONS
            if q["key"] not in answered_keys
        ]

        # Build the greeting prompt
        greeting_prompt = self._build_initial_greeting_prompt(
            current_answers=current_answers,
            company_name=company_name,
            missing_questions=missing_questions,
            source_context=source_context,
        )

        # Generate greeting
        if self.settings.mock_openai:
            if company_name:
                content = f"Welcome back! I see you're with {company_name}. I'm Autopilot, your robotics procurement consultant. Let's continue building your automation profile."
                chips = []
            else:
                content = "Hello! I'm Autopilot, your robotics procurement consultant. I'll help you discover the right cleaning automation for your facility. What is the name of your company?"
                chips = []
            result = {"content": content, "chips": chips, "ready_for_roi": False}
        else:
            try:
                response = self.client.chat.create(
                    model=self.settings.openai_model,
                    messages=[
                        {"role": "system", "content": greeting_prompt},
                        {"role": "user", "content": "Generate initial greeting"},
                    ],
                    response_format=DISCOVERY_RESPONSE_SCHEMA,
                    max_completion_tokens=300,
                    temperature=0.7,
                )
                result = json.loads(response.choices[0].message.content or "{}")

                if "content" not in result:
                    result["content"] = "Hello! I'm Autopilot, your robotics procurement consultant."
                if "chips" not in result:
                    result["chips"] = []
                if "ready_for_roi" not in result:
                    result["ready_for_roi"] = False

            except Exception as e:
                logger.error("Failed to generate initial greeting: %s", str(e))
                # Fallback greeting
                if company_name:
                    result = {
                        "content": f"Welcome! I see you're with {company_name}. I'm Autopilot, here to help you find the right cleaning automation.",
                        "chips": [],
                        "ready_for_roi": False,
                    }
                else:
                    result = {
                        "content": "Hello! I'm Autopilot, your robotics procurement consultant. I'll help you discover the right cleaning automation for your facility.",
                        "chips": [],
                        "ready_for_roi": False,
                    }

        # Save the greeting as a message
        msg_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=result["content"],
            metadata={
                "model": self.settings.openai_model,
                "chips": result["chips"],
                "ready_for_roi": result.get("ready_for_roi", False),
                "is_initial_greeting": True,
            },
        )

        msg_response = MessageResponse(
            id=msg_data["id"],
            conversation_id=msg_data["conversation_id"],
            role=msg_data["role"],
            content=msg_data["content"],
            metadata=msg_data.get("metadata", {}),
            created_at=msg_data["created_at"],
        )

        return {
            "content": result["content"],
            "chips": result["chips"],
            "message": msg_response,
        }

    def _build_initial_greeting_prompt(
        self,
        current_answers: dict[str, Any],
        company_name: str | None,
        missing_questions: list[dict[str, Any]],
        source_context: dict[str, Any] | None = None,
    ) -> str:
        """Build prompt for generating initial greeting.

        Args:
            current_answers: What we already know about this user.
            company_name: The user's company name if known.
            missing_questions: Questions we still need to ask.
            source_context: Optional context about referral source.

        Returns:
            str: System prompt for greeting generation.
        """
        # Format what we know
        if current_answers:
            known_info = "\n".join(
                f"- {key}: {ans.get('value', 'unknown')}"
                for key, ans in current_answers.items()
            )
            # Highlight company name specifically if known
            if company_name:
                known_info = f"COMPANY: {company_name}\n" + known_info
        else:
            known_info = "Nothing yet - this is a brand new user."

        # Format source context if available
        source_info = ""
        if source_context:
            source_type = source_context.get("source", "direct")
            if source_type == "email":
                source_info = "\nSOURCE: User arrived via email campaign. Reference the email content if relevant."
            elif source_type == "referral":
                referrer = source_context.get("referrer", "a colleague")
                source_info = f"\nSOURCE: User was referred by {referrer}. Acknowledge the referral warmly."
            elif source_type == "demo_request":
                source_info = "\nSOURCE: User requested a demo. They're actively evaluating solutions."

        # First question to ask
        first_question = missing_questions[0] if missing_questions else None
        next_question_guidance = ""
        if first_question:
            next_question_guidance = f"""
FIRST QUESTION TO ASK:
- Key: {first_question['key']}
- Question: "{first_question['question']}"
- Suggested chips: {first_question.get('chips', [])}
"""

        return f"""You are Autopilot, a premium robotics procurement consultant generating an initial greeting.

WHAT YOU KNOW ABOUT THIS USER:
{known_info}
{source_info}
{next_question_guidance}
INSTRUCTIONS:
1. Generate a warm, professional greeting
2. If you know the company name, acknowledge it naturally (don't ask again)
3. If you know other details (company type, facility info), reference them briefly
4. If this is a returning user with progress, acknowledge their journey
5. End with the first missing question woven in naturally (if any)
6. Keep it concise - 2-3 sentences max
7. Set chips to help the user respond (matching the question you're asking)
8. If all questions are answered, congratulate them and suggest viewing ROI

TONE: Premium, consultative, welcoming. Like a senior consultant greeting a valued client.

IMPORTANT: Your response must be valid JSON with content (string), chips (array), and ready_for_roi (boolean)."""

    async def generate_phase_transition_message(
        self,
        conversation_id: UUID,
        transition_type: str,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a dynamic message for phase transitions.

        Args:
            conversation_id: The conversation's UUID.
            transition_type: Type of transition ('discovery_to_roi' or 'roi_to_greenlight').
            session_id: Optional session ID for anonymous users.
            profile_id: Optional profile ID for authenticated users.
            context: Optional additional context (selected robot, ROI data, etc.)

        Returns:
            dict: {
                "content": str,  # The transition message
                "chips": list[str],  # Quick reply options
                "message": MessageResponse,  # The saved message
            }
        """
        # Gather context about what we know
        current_answers: dict[str, Any] = {}
        company_name: str | None = None
        selected_robot: dict[str, Any] | None = None

        if profile_id:
            from src.services.discovery_profile_service import DiscoveryProfileService
            from src.services.company_service import CompanyService

            discovery_service = DiscoveryProfileService()
            discovery_profile = await discovery_service.get_by_profile_id(profile_id)
            if discovery_profile:
                current_answers = discovery_profile.get("answers", {})
                # Get selected robot if available
                selected_ids = discovery_profile.get("selected_product_ids", [])
                if selected_ids:
                    robot_service = RobotCatalogService()
                    robots = await robot_service.get_robots_by_ids([UUID(id) for id in selected_ids[:1]])
                    if robots:
                        selected_robot = robots[0]

            # Check for company
            company_service = CompanyService()
            company = await company_service.get_user_company(profile_id)
            if company and company.get("name"):
                company_name = company["name"]
        elif session_id:
            session = await self.session_service.get_session_by_id(session_id)
            if session:
                current_answers = session.get("answers", {})
                if "company_name" in current_answers:
                    company_name = current_answers["company_name"].get("value")

        # Build the transition prompt based on type
        if transition_type == "discovery_to_roi":
            prompt = self._build_roi_transition_prompt(current_answers, company_name, selected_robot, context)
            default_chips = ["View Savings Breakdown", "Compare Options"]
        elif transition_type == "roi_to_greenlight":
            prompt = self._build_greenlight_transition_prompt(current_answers, company_name, selected_robot, context)
            default_chips = ["Set Target Date", "Invite Team"]
        else:
            raise ValueError(f"Unknown transition type: {transition_type}")

        # Generate message
        if self.settings.mock_openai:
            if transition_type == "discovery_to_roi":
                content = f"Excellent! Based on what you've shared about {company_name or 'your facility'}, I've prepared a detailed ROI analysis. Let's see how automation can transform your operations."
            else:
                content = f"Great progress! You're ready to move forward with deployment. Let's finalize the logistics - you can set a target start date, invite team members, and secure your lease."
            result = {"content": content, "chips": default_chips}
        else:
            try:
                response = self.client.chat.create(
                    model=self.settings.openai_model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Generate {transition_type} transition message"},
                    ],
                    response_format=DISCOVERY_RESPONSE_SCHEMA,
                    max_completion_tokens=300,
                    temperature=0.7,
                )
                result = json.loads(response.choices[0].message.content or "{}")

                if "content" not in result:
                    result["content"] = "Let's continue to the next step."
                if "chips" not in result:
                    result["chips"] = default_chips

            except Exception as e:
                logger.error("Failed to generate transition message: %s", str(e))
                # Fallback messages
                if transition_type == "discovery_to_roi":
                    result = {
                        "content": "I've compiled your discovery data into a comprehensive ROI model. Let's explore how automation can improve your facility's economics.",
                        "chips": default_chips,
                    }
                else:
                    result = {
                        "content": "You're ready for the final step. Let's finalize your deployment logistics and secure your implementation slot.",
                        "chips": default_chips,
                    }

        # Save the message
        msg_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=result["content"],
            metadata={
                "model": self.settings.openai_model,
                "chips": result["chips"],
                "transition_type": transition_type,
            },
        )

        msg_response = MessageResponse(
            id=msg_data["id"],
            conversation_id=msg_data["conversation_id"],
            role=msg_data["role"],
            content=msg_data["content"],
            metadata=msg_data.get("metadata", {}),
            created_at=msg_data["created_at"],
        )

        return {
            "content": result["content"],
            "chips": result["chips"],
            "message": msg_response,
        }

    def _build_roi_transition_prompt(
        self,
        current_answers: dict[str, Any],
        company_name: str | None,
        selected_robot: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> str:
        """Build prompt for ROI transition message."""
        # Format discovery summary
        discovery_summary = "\n".join(
            f"- {key}: {ans.get('value', 'unknown')}"
            for key, ans in current_answers.items()
        ) if current_answers else "Basic facility information collected"

        robot_info = ""
        if selected_robot:
            robot_info = f"""
SELECTED ROBOT:
- Name: {selected_robot.get('name', 'Unknown')}
- Category: {selected_robot.get('category', 'Cleaning Robot')}
- Monthly Lease: ${selected_robot.get('monthly_lease', 0):,.0f}
"""

        return f"""You are Autopilot, a premium robotics procurement consultant.

The user has completed discovery and is about to view the ROI analysis.

COMPANY: {company_name or 'Unknown'}

DISCOVERY DATA COLLECTED:
{discovery_summary}
{robot_info}
CONTEXT: The user clicked "Show Me" to view their ROI calculations. They're about to see how automation changes the economics of their facility.

INSTRUCTIONS:
1. Generate an enthusiastic but professional transition message
2. Acknowledge what you've learned about their facility (reference 1-2 specific details)
3. Build anticipation for the ROI insights they're about to see
4. Keep it to 2-3 sentences max
5. Set chips for next actions in the ROI view

TONE: Confident, consultative, value-focused. Like a consultant about to present compelling findings.

IMPORTANT: Your response must be valid JSON with content (string), chips (array), and ready_for_roi (boolean - set to true)."""

    def _build_greenlight_transition_prompt(
        self,
        current_answers: dict[str, Any],
        company_name: str | None,
        selected_robot: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> str:
        """Build prompt for Greenlight transition message."""
        robot_info = ""
        if selected_robot:
            robot_info = f"""
SELECTED ROBOT:
- Name: {selected_robot.get('name', 'Unknown')}
- Monthly Lease: ${selected_robot.get('monthly_lease', 0):,.0f}
"""

        return f"""You are Autopilot, a premium robotics procurement consultant.

The user has reviewed their ROI analysis and is ready to proceed to deployment.

COMPANY: {company_name or 'Unknown'}
{robot_info}
CONTEXT: The user is moving to the Greenlight phase where they will:
- Set a target deployment start date
- Invite team members to the project
- Finalize and purchase their robot lease

INSTRUCTIONS:
1. Generate an encouraging closing message
2. Acknowledge they've made great progress
3. Briefly outline what they'll do next (date, team, purchase)
4. Create urgency/excitement without being pushy
5. Keep it to 2-3 sentences max
6. Set chips that help them take action

TONE: Supportive, confident, closing-focused. Like a consultant guiding a client to a successful decision.

IMPORTANT: Your response must be valid JSON with content (string), chips (array), and ready_for_roi (boolean - can be false now)."""

    async def generate_discovery_response(
        self,
        conversation_id: UUID,
        user_message: str,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate an intelligent discovery response with chips.

        This method uses structured output to return the agent's response
        along with contextual chip options and readiness state.

        Uses asyncio.gather() to parallelize independent API calls for better latency.

        Args:
            conversation_id: The conversation's UUID.
            user_message: The user's message content.
            session_id: Optional session ID to get current answers (anonymous users).
            profile_id: Optional profile ID to get current answers (authenticated users).
            metadata: Optional metadata for the user message.

        Returns:
            dict: {
                "content": str,  # Agent's response
                "chips": list[str],  # Quick reply options
                "ready_for_roi": bool,  # Whether to show ROI
                "user_message": MessageResponse,
                "agent_message": MessageResponse,
            }
        """
        start_time = time.perf_counter()

        # ===== PHASE 1: Parallel fetch of context data =====
        # Load user context and robot catalog in parallel
        from src.services.discovery_profile_service import DiscoveryProfileService
        from src.services.company_service import CompanyService

        robot_catalog_service = RobotCatalogService()
        discovery_service = None
        current_answers: dict[str, Any] = {}

        async def fetch_robot_catalog() -> list[dict[str, Any]]:
            return await robot_catalog_service.list_robots(active_only=True)

        async def fetch_user_context() -> tuple[dict[str, Any], Any, dict | None]:
            """Fetch user context (answers, discovery_service, company)."""
            nonlocal discovery_service
            answers: dict[str, Any] = {}
            company: dict | None = None

            if profile_id:
                discovery_service = DiscoveryProfileService()
                company_service = CompanyService()

                # Parallel fetch of discovery profile and company
                profile_task = discovery_service.get_by_profile_id(profile_id)
                company_task = company_service.get_user_company(profile_id)
                discovery_profile, company = await asyncio.gather(
                    profile_task, company_task
                )

                logger.info(
                    "Discovery context lookup: profile_id=%s, found=%s, answers_count=%d",
                    profile_id,
                    discovery_profile is not None,
                    len(discovery_profile.get("answers", {})) if discovery_profile else 0,
                )
                if discovery_profile:
                    answers = discovery_profile.get("answers", {})
                    if answers:
                        logger.debug("Discovery answers keys: %s", list(answers.keys()))
                    else:
                        logger.warning(
                            "Discovery profile exists but has no answers for profile_id=%s",
                            profile_id,
                        )

                # Inject company_name if not present
                if "company_name" not in answers and company and company.get("name"):
                    answers["company_name"] = {
                        "questionId": 0,
                        "value": company["name"],
                        "label": "Company Name",
                        "key": "company_name",
                        "group": "Company",
                    }
                    logger.info("Injected company_name from user's company: %s", company["name"])

            elif session_id:
                session = await self.session_service.get_session_by_id(session_id)
                logger.info(
                    "Session context lookup: session_id=%s, found=%s, answers_count=%d",
                    session_id,
                    session is not None,
                    len(session.get("answers", {})) if session else 0,
                )
                if session:
                    answers = session.get("answers", {})

            return answers, discovery_service, company

        # Execute Phase 1 in parallel
        robot_catalog, (current_answers, discovery_service, _) = await asyncio.gather(
            fetch_robot_catalog(),
            fetch_user_context(),
        )

        phase1_time = time.perf_counter()
        logger.debug("Discovery Phase 1 (context fetch) took %.2fms", (phase1_time - start_time) * 1000)

        # Determine which required questions are still missing
        answered_keys = set(current_answers.keys())
        missing_questions = [
            q for q in REQUIRED_QUESTIONS
            if q["key"] not in answered_keys
        ]

        # ===== PHASE 2: Parallel store message + fetch recommendations + conversation history =====
        async def store_user_message() -> dict[str, Any]:
            return await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=user_message,
                metadata=metadata,
            )

        async def fetch_recommendations() -> Any:
            """Fetch recommendations if we have enough answers."""
            if len(answered_keys) < 4 or not current_answers:
                return None

            try:
                from src.schemas.roi import RecommendationsRequest, RecommendationsResponse
                from src.services.roi_service import get_roi_service

                # Check persistent cache first for authenticated users
                if profile_id and discovery_service:
                    cached = await discovery_service.get_cached_recommendations(
                        profile_id, current_answers
                    )
                    if cached:
                        try:
                            logger.info("Using cached recommendations for discovery context")
                            return RecommendationsResponse(**cached)
                        except Exception as e:
                            logger.warning("Failed to parse cached recommendations: %s", e)

                # Fetch fresh recommendations
                roi_service = get_roi_service()
                rec_request = RecommendationsRequest(answers=current_answers, top_k=3)
                recommendations = await roi_service.get_recommendations(
                    request=rec_request,
                    session_id=session_id,
                    profile_id=profile_id,
                    use_llm=True,
                )
                logger.debug("Fetched fresh recommendations for discovery context")

                # Cache recommendations for authenticated users (fire and forget)
                if profile_id and discovery_service and recommendations:
                    try:
                        await discovery_service.set_cached_recommendations(
                            profile_id,
                            current_answers,
                            recommendations.model_dump(mode="json"),
                        )
                    except Exception as cache_err:
                        logger.warning("Failed to cache recommendations: %s", cache_err)

                return recommendations
            except Exception as e:
                logger.warning("Failed to fetch recommendations for context: %s", str(e))
                return None

        async def fetch_conversation_history() -> list[dict[str, Any]]:
            return await self.conversation_service.get_recent_messages(
                conversation_id, limit=self.settings.max_context_messages
            )

        # Execute Phase 2 in parallel
        user_msg_data, current_recommendations, recent_messages = await asyncio.gather(
            store_user_message(),
            fetch_recommendations(),
            fetch_conversation_history(),
        )

        phase2_time = time.perf_counter()
        logger.debug("Discovery Phase 2 (message + recommendations) took %.2fms", (phase2_time - phase1_time) * 1000)

        user_msg_response = MessageResponse(
            id=user_msg_data["id"],
            conversation_id=user_msg_data["conversation_id"],
            role=user_msg_data["role"],
            content=user_msg_data["content"],
            metadata=user_msg_data.get("metadata", {}),
            created_at=user_msg_data["created_at"],
        )

        # Build discovery-specific prompt with robot catalog, recommendations, and current message
        # Pass current message so agent can recognize inline answers without pre-extraction
        system_prompt = self._build_discovery_prompt(
            current_answers, missing_questions, robot_catalog, current_recommendations, user_message
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Determine budget key and check token budget
        budget_key: str | None = None
        is_authenticated = False
        if profile_id:
            budget_key = f"user:{profile_id}"
            is_authenticated = True
        elif session_id:
            budget_key = f"session:{session_id}"

        # Generate response with structured output
        if self.settings.mock_openai:
            logger.info("Mock mode enabled - returning mock discovery response")
            # Return mock structured response
            next_q = missing_questions[0] if missing_questions else None
            result = {
                "content": f"Thanks for sharing! {next_q['question'] if next_q else 'I have enough information to show you ROI projections. Would you like to proceed?'}",
                "chips": next_q["chips"] if next_q and next_q["chips"] else [],
                "ready_for_roi": len(missing_questions) <= 2,
            }
        else:
            # Check token budget before making API call
            if budget_key:
                token_budget = get_token_budget()
                # Estimate tokens: rough estimate of input + max output
                estimated_tokens = len(user_message) // 4 + 500  # ~4 chars per token
                allowed, remaining, limit = await token_budget.check_budget(
                    budget_key, estimated_tokens, is_authenticated
                )
                if not allowed:
                    raise TokenBudgetError(
                        message="Daily token budget exceeded. Please try again tomorrow.",
                        tokens_used=limit - remaining,
                        daily_limit=limit,
                    )

            try:
                response = self.client.chat.create(
                    model=self.settings.openai_model,
                    messages=messages,  # type: ignore[arg-type]
                    response_format=DISCOVERY_RESPONSE_SCHEMA,
                    max_completion_tokens=500,
                    temperature=0.7,
                )

                result = json.loads(response.choices[0].message.content or "{}")

                # Track actual token usage
                if budget_key and response.usage:
                    total_tokens = response.usage.total_tokens
                    await token_budget.record_usage(budget_key, total_tokens)
                    logger.debug(
                        "Token usage recorded: %d tokens for %s",
                        total_tokens,
                        budget_key,
                    )

                # Ensure required fields exist
                if "content" not in result:
                    result["content"] = "I'd love to learn more about your needs."
                if "chips" not in result:
                    result["chips"] = []
                if "ready_for_roi" not in result:
                    result["ready_for_roi"] = False

            except OpenAIError as e:
                logger.error("OpenAI API error in discovery: %s", str(e))
                result = {
                    "content": "I apologize, but I'm having trouble right now. Please try again.",
                    "chips": [],
                    "ready_for_roi": False,
                }
            except json.JSONDecodeError as e:
                logger.error("JSON decode error in discovery response: %s", str(e))
                result = {
                    "content": "Let me try that again. What would you like to tell me about your facility?",
                    "chips": [],
                    "ready_for_roi": False,
                }

        # Store agent response with chips in metadata
        agent_msg_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=result["content"],
            metadata={
                "model": self.settings.openai_model,
                "chips": result["chips"],
                "ready_for_roi": result["ready_for_roi"],
            },
        )

        agent_msg_response = MessageResponse(
            id=agent_msg_data["id"],
            conversation_id=agent_msg_data["conversation_id"],
            role=agent_msg_data["role"],
            content=agent_msg_data["content"],
            metadata=agent_msg_data.get("metadata", {}),
            created_at=agent_msg_data["created_at"],
        )

        return {
            "content": result["content"],
            "chips": result["chips"],
            "ready_for_roi": result["ready_for_roi"],
            "user_message": user_msg_response,
            "agent_message": agent_msg_response,
        }
