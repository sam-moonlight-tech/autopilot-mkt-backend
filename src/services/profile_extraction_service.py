"""Service for AI-powered extraction of discovery profile data from conversations."""

import json
import logging
from typing import Any
from uuid import UUID

from openai import OpenAIError

from src.core.openai import get_openai_client
from src.services.conversation_service import ConversationService
from src.services.discovery_profile_service import DiscoveryProfileService
from src.services.extraction_constants import (
    EXTRACTION_SCHEMA,
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT,
    QUESTION_BY_KEY,
)
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)


class ProfileExtractionService:
    """Service for extracting discovery data from conversation content."""

    EXTRACTION_MODEL = "gpt-4o"  # Best structured output support with strict mode
    MAX_MESSAGES_FOR_EXTRACTION = 10  # Last N messages to analyze

    def __init__(
        self,
        conversation_service: ConversationService | None = None,
        session_service: SessionService | None = None,
        discovery_profile_service: DiscoveryProfileService | None = None,
    ) -> None:
        """Initialize profile extraction service.

        Args:
            conversation_service: Optional conversation service for testing.
            session_service: Optional session service for testing.
            discovery_profile_service: Optional discovery profile service for testing.
        """
        self.client = get_openai_client()
        self.conversation_service = conversation_service or ConversationService()
        self.session_service = session_service or SessionService()
        self.discovery_profile_service = (
            discovery_profile_service or DiscoveryProfileService()
        )

    async def extract_and_update(
        self,
        conversation_id: UUID,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Extract discovery data from conversation and update session/profile.

        Args:
            conversation_id: The conversation to analyze.
            session_id: Anonymous user's session ID (for sessions table).
            profile_id: Authenticated user's profile ID (for discovery_profiles table).

        Returns:
            dict: Extraction results with extracted_count, confidence, and keys.
        """
        if not session_id and not profile_id:
            logger.warning("No session_id or profile_id provided for extraction")
            return {"extracted_count": 0, "reason": "No target provided"}

        try:
            # 1. Get recent messages
            messages = await self.conversation_service.get_recent_messages(
                conversation_id, limit=self.MAX_MESSAGES_FOR_EXTRACTION
            )

            if len(messages) < 2:
                return {"extracted_count": 0, "reason": "Not enough messages"}

            # 2. Get current answers
            current_answers = await self._get_current_answers(session_id, profile_id)

            # 3. Extract new data
            extraction_result = await self._extract_from_messages(
                messages, current_answers
            )

            if not extraction_result.get("answers"):
                return {"extracted_count": 0, "reason": "No new data extracted"}

            # 4. Validate and enrich extracted answers
            validated_answers = self._validate_and_enrich_answers(
                extraction_result["answers"]
            )

            if not validated_answers:
                return {"extracted_count": 0, "reason": "No valid answers extracted"}

            # 5. Merge and update
            merged_answers = {**current_answers, **validated_answers}

            await self._update_target(
                session_id=session_id,
                profile_id=profile_id,
                answers=merged_answers,
                roi_inputs=extraction_result.get("roi_inputs"),
            )

            logger.info(
                "Extracted %d answers from conversation %s: %s",
                len(validated_answers),
                conversation_id,
                list(validated_answers.keys()),
            )

            return {
                "extracted_count": len(validated_answers),
                "confidence": extraction_result.get("extraction_confidence", "medium"),
                "keys_extracted": list(validated_answers.keys()),
            }

        except Exception as e:
            logger.error("Extraction failed for conversation %s: %s", conversation_id, e)
            return {"extracted_count": 0, "error": str(e)}

    async def _get_current_answers(
        self,
        session_id: UUID | None,
        profile_id: UUID | None,
    ) -> dict[str, Any]:
        """Get current answers from session or discovery profile."""
        if session_id:
            session = await self.session_service.get_session_by_id(session_id)
            return session.get("answers", {}) if session else {}
        elif profile_id:
            profile = await self.discovery_profile_service.get_by_profile_id(profile_id)
            return profile.get("answers", {}) if profile else {}
        return {}

    async def _extract_from_messages(
        self,
        messages: list[dict[str, Any]],
        current_answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Call OpenAI to extract structured data from messages.

        Returns dict with 'answers' as a dict keyed by question key (converted from array).
        """
        # Build conversation text
        conversation_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in messages
        )

        # Build current answers summary
        current_summary = (
            "\n".join(
                f"- {key}: {ans.get('value', 'unknown')}"
                for key, ans in current_answers.items()
            )
            or "No data extracted yet."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": EXTRACTION_USER_PROMPT.format(
                            current_answers=current_summary,
                            conversation_messages=conversation_text,
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "discovery_extraction",
                        "schema": EXTRACTION_SCHEMA,
                        "strict": True,
                    },
                },
                temperature=0.0,  # Zero temp for deterministic extraction
                max_completion_tokens=2000,
            )

            content = response.choices[0].message.content or "{}"
            result = json.loads(content)

            # Convert answers array to dict keyed by question key
            answers_array = result.get("answers", [])
            answers_dict = {ans["key"]: ans for ans in answers_array if ans.get("key")}

            return {
                "answers": answers_dict,
                "roi_inputs": result.get("roi_inputs"),
                "extraction_confidence": result.get("extraction_confidence", "medium"),
            }

        except OpenAIError as e:
            logger.error("OpenAI extraction error: %s", str(e))
            return {"answers": {}, "error": str(e)}
        except json.JSONDecodeError as e:
            logger.error("JSON decode error in extraction: %s", str(e))
            return {"answers": {}, "error": str(e)}

    def _validate_and_enrich_answers(
        self,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate extracted answers and enrich with question metadata."""
        validated = {}

        for key, answer in answers.items():
            # Check if key is valid
            if key not in QUESTION_BY_KEY:
                logger.warning("Unknown question key extracted: %s", key)
                continue

            # Ensure required fields exist
            if not answer.get("value"):
                continue

            # Enrich with question metadata if missing
            question = QUESTION_BY_KEY[key]
            validated[key] = {
                "questionId": answer.get("questionId", question["id"]),
                "key": key,
                "label": answer.get("label", question["label"]),
                "value": str(answer["value"]),
                "group": answer.get("group", question["group"]),
            }

        return validated

    async def _update_target(
        self,
        session_id: UUID | None,
        profile_id: UUID | None,
        answers: dict[str, Any],
        roi_inputs: dict[str, Any] | None,
    ) -> None:
        """Update session or discovery profile with extracted data."""
        if session_id:
            from src.schemas.session import ROIInputsSchema, SessionUpdate

            update_data = SessionUpdate(answers=answers)
            if roi_inputs:
                # Filter to only valid ROI fields
                valid_roi = {
                    k: v
                    for k, v in roi_inputs.items()
                    if k in ("laborRate", "manualMonthlySpend", "manualMonthlyHours")
                    and v is not None
                }
                if valid_roi:
                    # Fill in defaults for missing required fields
                    full_roi = {
                        "laborRate": valid_roi.get("laborRate", 0),
                        "utilization": 0.8,  # Default
                        "maintenanceFactor": 0.1,  # Default
                        "manualMonthlySpend": valid_roi.get("manualMonthlySpend", 0),
                        "manualMonthlyHours": valid_roi.get("manualMonthlyHours", 0),
                    }
                    update_data.roi_inputs = ROIInputsSchema(**full_roi)
            await self.session_service.update_session(session_id, update_data)

        elif profile_id:
            from src.schemas.discovery import DiscoveryProfileUpdate
            from src.schemas.session import ROIInputsSchema

            update_data = DiscoveryProfileUpdate(answers=answers)
            if roi_inputs:
                valid_roi = {
                    k: v
                    for k, v in roi_inputs.items()
                    if k in ("laborRate", "manualMonthlySpend", "manualMonthlyHours")
                    and v is not None
                }
                if valid_roi:
                    full_roi = {
                        "laborRate": valid_roi.get("laborRate", 0),
                        "utilization": 0.8,
                        "maintenanceFactor": 0.1,
                        "manualMonthlySpend": valid_roi.get("manualMonthlySpend", 0),
                        "manualMonthlyHours": valid_roi.get("manualMonthlyHours", 0),
                    }
                    update_data.roi_inputs = ROIInputsSchema(**full_roi)
            await self.discovery_profile_service.update(profile_id, update_data)
