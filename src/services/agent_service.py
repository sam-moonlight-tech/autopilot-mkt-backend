"""Agent service for OpenAI-powered conversations."""

import json
import logging
from typing import Any
from uuid import UUID

from openai import OpenAIError

from src.core.config import get_settings
from src.core.openai import get_openai_client
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
    ) -> tuple[MessageResponse, MessageResponse]:
        """Generate an agent response to a user message.

        Stores both the user message and agent response.

        Args:
            conversation_id: The conversation's UUID.
            user_message: The user's message content.
            metadata: Optional metadata for the user message.

        Returns:
            tuple: (user_message_response, agent_message_response)

        Raises:
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

        # Check if mock mode is enabled
        if self.settings.mock_openai:
            logger.info("Mock mode enabled - returning mock response")
            agent_content = self._get_mock_response(phase, user_message)
        else:
            try:
                # Call OpenAI API
                response = self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=context,  # type: ignore[arg-type]
                    max_completion_tokens=1000,
                    temperature=0.7,
                )

                agent_content = response.choices[0].message.content or ""

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

    def _build_discovery_prompt(
        self,
        current_answers: dict[str, Any],
        missing_questions: list[dict[str, Any]],
        robot_catalog: list[dict[str, Any]],
    ) -> str:
        """Build an intelligent discovery system prompt.

        The prompt tells the agent what's already known, what still needs
        to be gathered, and what robots are available in the catalog.

        Args:
            current_answers: Dict of already answered questions.
            missing_questions: List of required questions not yet answered.
            robot_catalog: List of available robots in the catalog.

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

        return f"""You are Autopilot, a premium robotics procurement consultant.

AVAILABLE ROBOT CATALOG (ONLY recommend from this list):
{catalog_summary}

WHAT YOU KNOW ABOUT THIS CUSTOMER:
{answered_summary}

STILL NEED TO LEARN ({remaining_count} remaining):
{missing_summary}

INSTRUCTIONS:
1. Acknowledge what the user just said naturally and warmly
2. If there are missing questions, weave ONE into your response conversationally
3. If the user's message ALREADY contains info about missing topics, acknowledge it - don't re-ask
4. Set ready_for_roi=true ONLY when you have answers for most required questions (4+ of 6)
5. Return chips matching the question you're asking, or empty array for open-ended questions
6. When discussing specific robots, ONLY mention robots from the AVAILABLE ROBOT CATALOG above
7. NEVER make up or hallucinate robot models - if asked about specific models, only reference the catalog

TONE: Premium, consultative, efficient. Like a senior consultant who values the client's time.
Don't be robotic or interrogative. If user gives rich context, adapt and skip redundant questions.

IMPORTANT: Your response must be valid JSON with content (string), chips (array), and ready_for_roi (boolean)."""

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
        # Get current answers from session or discovery profile
        current_answers: dict[str, Any] = {}
        if profile_id:
            # Authenticated user - get answers from discovery profile
            from src.services.discovery_profile_service import DiscoveryProfileService
            discovery_service = DiscoveryProfileService()
            discovery_profile = await discovery_service.get_by_profile_id(profile_id)
            if discovery_profile:
                current_answers = discovery_profile.get("answers", {})
        elif session_id:
            # Anonymous user - get answers from session
            session = await self.session_service.get_session_by_id(session_id)
            if session:
                current_answers = session.get("answers", {})

        # Determine which required questions are still missing
        answered_keys = set(current_answers.keys())
        missing_questions = [
            q for q in REQUIRED_QUESTIONS
            if q["key"] not in answered_keys
        ]

        # Fetch robot catalog for context
        robot_catalog_service = RobotCatalogService()
        robot_catalog = await robot_catalog_service.list_robots(active_only=True)

        # Store user message
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

        # Build discovery-specific prompt with robot catalog
        system_prompt = self._build_discovery_prompt(
            current_answers, missing_questions, robot_catalog
        )

        # Get conversation history
        recent_messages = await self.conversation_service.get_recent_messages(
            conversation_id, limit=self.settings.max_context_messages
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

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
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=messages,  # type: ignore[arg-type]
                    response_format=DISCOVERY_RESPONSE_SCHEMA,
                    max_completion_tokens=500,
                    temperature=0.7,
                )

                result = json.loads(response.choices[0].message.content or "{}")

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
