"""Unit tests for ProfileExtractionService."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.services.profile_extraction_service import ProfileExtractionService


class TestExtractAndUpdate:
    """Tests for extract_and_update method."""

    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response with array format."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "answers": [
                {
                    "questionId": 7,
                    "key": "sqft",
                    "label": "Total Sq Ft",
                    "value": "50000",
                    "group": "Facility"
                }
            ],
            "roi_inputs": {
                "laborRate": None,
                "manualMonthlySpend": None,
                "manualMonthlyHours": None
            },
            "extraction_confidence": "high"
        })
        return mock_response

    @pytest.mark.asyncio
    async def test_extracts_facility_size_from_conversation(self, mock_openai_response):
        """Test extraction of facility size from user message."""
        mock_openai = MagicMock()
        mock_openai.chat.create.return_value = mock_openai_response

        mock_conv_service = MagicMock()
        mock_conv_service.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "Our facility is about 50000 square feet"},
            {"role": "assistant", "content": "That's a good size facility!"},
        ])

        mock_session_service = MagicMock()
        mock_session_service.get_session_by_id = AsyncMock(return_value={"answers": {}})
        mock_session_service.update_session = AsyncMock()

        with patch("src.services.profile_extraction_service.get_openai_client", return_value=mock_openai):
            service = ProfileExtractionService(
                conversation_service=mock_conv_service,
                session_service=mock_session_service,
            )
            result = await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                session_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
            )

            assert result["extracted_count"] == 1
            assert "sqft" in result["keys_extracted"]
            mock_session_service.update_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_enough_messages(self):
        """Test that extraction returns early when conversation is too short."""
        mock_conv_service = MagicMock()
        mock_conv_service.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
        ])

        mock_session_service = MagicMock()

        with patch("src.services.profile_extraction_service.get_openai_client"):
            service = ProfileExtractionService(
                conversation_service=mock_conv_service,
                session_service=mock_session_service,
            )
            result = await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                session_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
            )

            assert result["extracted_count"] == 0
            assert result["reason"] == "Not enough messages"

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_target_provided(self):
        """Test that extraction returns early when no session_id or profile_id."""
        with patch("src.services.profile_extraction_service.get_openai_client"):
            service = ProfileExtractionService()
            result = await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            )

            assert result["extracted_count"] == 0
            assert result["reason"] == "No target provided"

    @pytest.mark.asyncio
    async def test_merges_with_existing_answers(self, mock_openai_response):
        """Test that new extractions merge with existing answers."""
        mock_openai = MagicMock()
        mock_openai.chat.create.return_value = mock_openai_response

        mock_conv_service = MagicMock()
        mock_conv_service.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "50000 sqft facility"},
            {"role": "assistant", "content": "Got it!"},
        ])

        existing_answers = {
            "company_name": {
                "questionId": 1,
                "key": "company_name",
                "label": "Company Name",
                "value": "Acme Corp",
                "group": "Company"
            }
        }

        mock_session_service = MagicMock()
        mock_session_service.get_session_by_id = AsyncMock(return_value={"answers": existing_answers})
        mock_session_service.update_session = AsyncMock()

        with patch("src.services.profile_extraction_service.get_openai_client", return_value=mock_openai):
            service = ProfileExtractionService(
                conversation_service=mock_conv_service,
                session_service=mock_session_service,
            )
            await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                session_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
            )

            # Verify update was called with merged answers
            call_args = mock_session_service.update_session.call_args
            update_data = call_args[0][1]  # Second positional arg is the update data
            assert "company_name" in update_data.answers
            assert "sqft" in update_data.answers

    @pytest.mark.asyncio
    async def test_handles_extraction_failure_gracefully(self):
        """Test that extraction failures don't raise exceptions."""
        mock_openai = MagicMock()
        mock_openai.chat.create.side_effect = Exception("API Error")

        mock_conv_service = MagicMock()
        mock_conv_service.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ])

        mock_session_service = MagicMock()
        mock_session_service.get_session_by_id = AsyncMock(return_value={"answers": {}})

        with patch("src.services.profile_extraction_service.get_openai_client", return_value=mock_openai):
            service = ProfileExtractionService(
                conversation_service=mock_conv_service,
                session_service=mock_session_service,
            )
            result = await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                session_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
            )

            assert result["extracted_count"] == 0
            assert "error" in result


class TestValidateAndEnrichAnswers:
    """Tests for _validate_and_enrich_answers method."""

    def test_validates_known_question_keys(self):
        """Test that only valid question keys are accepted."""
        with patch("src.services.profile_extraction_service.get_openai_client"):
            service = ProfileExtractionService()
            answers = {
                "sqft": {"value": "50000", "questionId": 7, "label": "Total Sq Ft", "group": "Facility"},
                "invalid_key": {"value": "test", "questionId": 99, "label": "Invalid", "group": "Company"},
            }
            result = service._validate_and_enrich_answers(answers)

            assert "sqft" in result
            assert "invalid_key" not in result

    def test_enriches_answers_with_question_metadata(self):
        """Test that answers are enriched with question metadata."""
        with patch("src.services.profile_extraction_service.get_openai_client"):
            service = ProfileExtractionService()
            answers = {
                "sqft": {"value": "50000"},  # Missing other fields
            }
            result = service._validate_and_enrich_answers(answers)

            assert result["sqft"]["questionId"] == 7
            assert result["sqft"]["label"] == "Total Sq Ft"
            assert result["sqft"]["group"] == "Facility"

    def test_skips_answers_without_value(self):
        """Test that answers without a value are skipped."""
        with patch("src.services.profile_extraction_service.get_openai_client"):
            service = ProfileExtractionService()
            answers = {
                "sqft": {"value": "50000"},
                "courts_count": {"value": ""},  # Empty value
            }
            result = service._validate_and_enrich_answers(answers)

            assert "sqft" in result
            assert "courts_count" not in result


class TestROIInputsExtraction:
    """Tests for ROI inputs extraction."""

    @pytest.mark.asyncio
    async def test_extracts_roi_inputs(self):
        """Test extraction of ROI inputs from conversation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "answers": [
                {
                    "questionId": 11,
                    "key": "monthly_spend",
                    "label": "Monthly Spend",
                    "value": "5000",
                    "group": "Economics"
                }
            ],
            "roi_inputs": {
                "laborRate": 18.0,
                "manualMonthlySpend": 5000.0,
                "manualMonthlyHours": 160.0
            },
            "extraction_confidence": "high"
        })

        mock_openai = MagicMock()
        mock_openai.chat.create.return_value = mock_response

        mock_conv_service = MagicMock()
        mock_conv_service.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "We spend $5000/month on cleaning, about 40 hours/week at $18/hour"},
            {"role": "assistant", "content": "That's significant labor cost."},
        ])

        mock_session_service = MagicMock()
        mock_session_service.get_session_by_id = AsyncMock(return_value={"answers": {}})
        mock_session_service.update_session = AsyncMock()

        with patch("src.services.profile_extraction_service.get_openai_client", return_value=mock_openai):
            service = ProfileExtractionService(
                conversation_service=mock_conv_service,
                session_service=mock_session_service,
            )
            result = await service.extract_and_update(
                conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                session_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
            )

            assert result["extracted_count"] == 1
            # Verify ROI inputs were included in update
            call_args = mock_session_service.update_session.call_args
            update_data = call_args[0][1]
            assert update_data.roi_inputs is not None
            assert update_data.roi_inputs.laborRate == 18.0
