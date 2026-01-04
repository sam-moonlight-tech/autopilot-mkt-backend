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

logger = logging.getLogger(__name__)

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
    ConversationPhase.SELECTION: """You are Autopilot, an expert robotics procurement consultant helping companies select the right robotics solutions.

Your role in the Selection phase:
- Recommend specific product categories based on their needs
- Discuss features, specifications, and trade-offs
- Help compare different options
- Guide them toward making informed decisions

Guidelines:
- Base recommendations on information gathered in discovery
- Consider their ROI requirements from the previous phase
- Present options clearly with pros and cons
- Be ready to provide product recommendations from our catalog""",
    ConversationPhase.COMPLETED: """You are Autopilot, an expert robotics procurement consultant.

This conversation has been completed. The user has made their selections. You can:
- Answer any follow-up questions
- Provide additional information about selected products
- Help with next steps for procurement
- Summarize the conversation if requested""",
}


class AgentService:
    """Service for AI agent interactions."""

    def __init__(self, rag_service: RAGService | None = None) -> None:
        """Initialize agent service.

        Args:
            rag_service: Optional RAG service for testing.
        """
        self.client = get_openai_client()
        self.settings = get_settings()
        self.conversation_service = ConversationService()
        self._rag_service = rag_service

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    def get_system_prompt(self, phase: ConversationPhase) -> str:
        """Get the system prompt for a conversation phase.

        Args:
            phase: The current conversation phase.

        Returns:
            str: The system prompt for the phase.
        """
        return SYSTEM_PROMPTS.get(phase, SYSTEM_PROMPTS[ConversationPhase.DISCOVERY])

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

        # Add RAG context for selection phase or when user asks about products
        if current_message and phase in (
            ConversationPhase.SELECTION,
            ConversationPhase.ROI,
        ):
            product_context = await self.rag_service.get_relevant_products_for_context(
                query=current_message,
                top_k=5,
            )
            if product_context:
                system_prompt += f"\n\n{product_context}"

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

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=context,  # type: ignore[arg-type]
                max_tokens=1000,
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
