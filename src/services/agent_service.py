"""Agent service for OpenAI-powered conversations."""

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
from src.services.rag_service import RAGService, get_rag_service
from src.services.sales_knowledge_service import SalesKnowledgeService, get_sales_knowledge_service

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


class AgentService:
    """Service for AI agent interactions."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        sales_knowledge_service: SalesKnowledgeService | None = None,
    ) -> None:
        """Initialize agent service.

        Args:
            rag_service: Optional RAG service for testing.
            sales_knowledge_service: Optional sales knowledge service for testing.
        """
        self.client = get_openai_client()
        self.settings = get_settings()
        self.conversation_service = ConversationService()
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
