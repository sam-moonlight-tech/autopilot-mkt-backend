"""Session business logic service."""

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.session import SessionUpdate

if TYPE_CHECKING:
    from src.services.checkout_service import CheckoutService


class SessionService:
    """Service for managing anonymous user sessions."""

    TOKEN_LENGTH = 64  # Length of session token in characters

    def __init__(self, checkout_service: "CheckoutService | None" = None) -> None:
        """Initialize session service with Supabase client.

        Args:
            checkout_service: Optional checkout service for order transfer on claim.
        """
        self.client = get_supabase_client()
        self._checkout_service = checkout_service

    def _generate_token(self) -> str:
        """Generate a cryptographically secure session token.

        Returns:
            str: A 64-character hex token.
        """
        return secrets.token_hex(self.TOKEN_LENGTH // 2)

    async def create_session(self) -> tuple[dict[str, Any], str]:
        """Create a new session with a unique token.

        Returns:
            tuple: (session_data, session_token)
        """
        token = self._generate_token()

        session_data = {
            "session_token": token,
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "selected_product_ids": [],
            "metadata": {},
        }

        response = (
            self.client.table("sessions")
            .insert(session_data)
            .execute()
        )

        return response.data[0], token

    async def get_session_by_token(self, token: str) -> dict[str, Any] | None:
        """Get a session by its token.

        Args:
            token: The session token from cookie.

        Returns:
            dict | None: The session data or None if not found.
        """
        response = (
            self.client.table("sessions")
            .select("*")
            .eq("session_token", token)
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def get_session_by_id(self, session_id: UUID) -> dict[str, Any] | None:
        """Get a session by its ID.

        Args:
            session_id: The session UUID.

        Returns:
            dict | None: The session data or None if not found.
        """
        response = (
            self.client.table("sessions")
            .select("*")
            .eq("id", str(session_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def update_session(
        self,
        session_id: UUID,
        data: SessionUpdate,
    ) -> dict[str, Any] | None:
        """Update a session.

        Args:
            session_id: The session UUID.
            data: The fields to update.

        Returns:
            dict | None: The updated session data or None if not found.
        """
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Convert nested Pydantic models to dicts for JSONB storage
        if "answers" in update_data:
            update_data["answers"] = {
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in update_data["answers"].items()
            }
        if "roi_inputs" in update_data and update_data["roi_inputs"]:
            roi = update_data["roi_inputs"]
            update_data["roi_inputs"] = roi.model_dump() if hasattr(roi, "model_dump") else roi

        # Convert UUID list to string list for PostgreSQL
        if "selected_product_ids" in update_data:
            update_data["selected_product_ids"] = [
                str(uid) for uid in update_data["selected_product_ids"]
            ]

        if not update_data:
            # No changes, return current session
            return await self.get_session_by_id(session_id)

        response = (
            self.client.table("sessions")
            .update(update_data)
            .eq("id", str(session_id))
            .execute()
        )

        return response.data[0] if response.data else None

    async def is_session_valid(self, token: str) -> bool:
        """Check if a session token is valid and not expired.

        Args:
            token: The session token to validate.

        Returns:
            bool: True if session is valid and not expired.
        """
        session = await self.get_session_by_token(token)

        if not session:
            return False

        # Check if session is expired
        expires_at = session.get("expires_at")
        if expires_at:
            # Parse the timestamp string
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                return False

        # Check if session has been claimed
        if session.get("claimed_by_profile_id"):
            return False

        return True

    async def set_conversation(
        self,
        session_id: UUID,
        conversation_id: UUID,
    ) -> dict[str, Any] | None:
        """Set the conversation ID for a session.

        Args:
            session_id: The session UUID.
            conversation_id: The conversation UUID to link.

        Returns:
            dict | None: The updated session data or None if not found.
        """
        response = (
            self.client.table("sessions")
            .update({"conversation_id": str(conversation_id)})
            .eq("id", str(session_id))
            .execute()
        )

        return response.data[0] if response.data else None

    async def claim_session(
        self,
        session_id: UUID,
        profile_id: UUID,
    ) -> dict[str, Any]:
        """Claim a session and merge its data to a user profile.

        This transfers all session data (answers, ROI inputs, selections) to
        the user's discovery profile, transfers conversation ownership, and
        transfers any orders to the user's profile.

        Args:
            session_id: The session UUID to claim.
            profile_id: The profile UUID to claim the session for.

        Returns:
            dict: Result containing discovery_profile, conversation_transferred,
                and orders_transferred count.

        Raises:
            ValueError: If session not found, already claimed, or expired.
        """
        # Get the session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise ValueError("Session not found")

        # Check if already claimed
        if session.get("claimed_by_profile_id"):
            raise ValueError("Session has already been claimed")

        # Check if expired
        expires_at = session.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                raise ValueError("Session has expired")

        # Create or update discovery profile with session data
        discovery_profile = await self._create_or_update_discovery_profile(
            profile_id=profile_id,
            session=session,
        )

        # Transfer conversation ownership if exists
        conversation_transferred = False
        conversation_id = session.get("conversation_id")
        if conversation_id:
            await self._transfer_conversation_ownership(
                conversation_id=UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                profile_id=profile_id,
            )
            conversation_transferred = True

        # Transfer orders to the profile if checkout service is available
        orders_transferred = 0
        if self._checkout_service:
            orders_transferred = await self._checkout_service.transfer_orders_to_profile(
                session_id=session_id,
                profile_id=profile_id,
            )

        # Mark session as claimed
        self.client.table("sessions").update(
            {"claimed_by_profile_id": str(profile_id)}
        ).eq("id", str(session_id)).execute()

        return {
            "discovery_profile": discovery_profile,
            "conversation_transferred": conversation_transferred,
            "orders_transferred": orders_transferred,
        }

    async def _create_or_update_discovery_profile(
        self,
        profile_id: UUID,
        session: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update a discovery profile from session data.

        Args:
            profile_id: The profile UUID.
            session: The session data to copy.

        Returns:
            dict: The created or updated discovery profile.
        """
        # Check if discovery profile exists
        existing = (
            self.client.table("discovery_profiles")
            .select("*")
            .eq("profile_id", str(profile_id))
            .execute()
        )

        profile_data = {
            "current_question_index": session.get("current_question_index", 0),
            "phase": session.get("phase", "discovery"),
            "answers": session.get("answers", {}),
            "roi_inputs": session.get("roi_inputs"),
            "selected_product_ids": session.get("selected_product_ids", []),
            "timeframe": session.get("timeframe"),
        }

        if existing.data:
            # Update existing profile
            response = (
                self.client.table("discovery_profiles")
                .update(profile_data)
                .eq("profile_id", str(profile_id))
                .execute()
            )
        else:
            # Create new profile
            profile_data["profile_id"] = str(profile_id)
            response = (
                self.client.table("discovery_profiles")
                .insert(profile_data)
                .execute()
            )

        return response.data[0]

    async def _transfer_conversation_ownership(
        self,
        conversation_id: UUID,
        profile_id: UUID,
    ) -> None:
        """Transfer conversation ownership from session to user profile.

        Args:
            conversation_id: The conversation UUID.
            profile_id: The profile UUID to transfer to.
        """
        # Get the user_id from the profile
        profile_response = (
            self.client.table("profiles")
            .select("user_id")
            .eq("id", str(profile_id))
            .maybe_single()
            .execute()
        )

        if profile_response.data:
            user_id = profile_response.data["user_id"]
            # Update conversation to be owned by the user instead of session
            self.client.table("conversations").update(
                {"user_id": str(user_id), "session_id": None}
            ).eq("id", str(conversation_id)).execute()

    async def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions to prevent table bloat.

        Removes all sessions where expires_at is in the past.

        Returns:
            int: Number of sessions deleted.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Delete expired sessions and get the count
        response = (
            self.client.table("sessions")
            .delete()
            .lt("expires_at", now)
            .execute()
        )

        return len(response.data) if response.data else 0
