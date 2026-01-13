"""Intelligent robot recommendation service using LLM and semantic search."""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from openai import OpenAIError

from src.core.config import get_settings
from src.core.openai import get_openai_client
from src.core.token_budget import TokenBudgetError, get_token_budget
from src.models.session import DiscoveryAnswer
from src.schemas.roi import (
    OtherRobotOption,
    RecommendationReason,
    RecommendationsRequest,
    RecommendationsResponse,
    RobotRecommendation,
    ROIInputs,
)
from src.services.rag_service import RAGService, get_rag_service
from src.services.recommendation_cache import get_recommendation_cache
from src.services.recommendation_prompts import (
    LLM_SCORING_SCHEMA,
    SCORING_SYSTEM_PROMPT,
    SCORING_USER_PROMPT_TEMPLATE,
    format_discovery_context,
    format_robots_context,
)
from src.services.robot_catalog_service import RobotCatalogService

logger = logging.getLogger(__name__)

# Algorithm version for LLM-powered recommendations
LLM_ALGORITHM_VERSION = "2.0.0"


class RecommendationService:
    """Service for intelligent robot recommendations using LLM and RAG."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        robot_catalog_service: RobotCatalogService | None = None,
    ) -> None:
        """Initialize recommendation service.

        Args:
            rag_service: Optional RAG service for testing.
            robot_catalog_service: Optional robot catalog service for testing.
        """
        self._rag_service = rag_service
        self._robot_catalog_service = robot_catalog_service
        self.settings = get_settings()
        self.client = get_openai_client()

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    @property
    def robot_catalog(self) -> RobotCatalogService:
        """Get robot catalog service."""
        if self._robot_catalog_service is None:
            self._robot_catalog_service = RobotCatalogService()
        return self._robot_catalog_service

    async def get_intelligent_recommendations(
        self,
        request: RecommendationsRequest,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
        use_cache: bool = True,
    ) -> RecommendationsResponse:
        """Get intelligent robot recommendations using LLM scoring.

        Args:
            request: Recommendations request with answers.
            session_id: Optional session ID for token budget tracking.
            profile_id: Optional profile ID for token budget tracking.
            use_cache: Whether to use cached recommendations.

        Returns:
            RecommendationsResponse with ranked recommendations.

        Raises:
            TokenBudgetError: If daily token budget is exceeded (will fallback).
        """
        # Check cache first
        if use_cache:
            cache = get_recommendation_cache()
            cached = cache.get(request.answers)
            if cached:
                logger.info("Returning cached recommendations")
                return cached

        try:
            # Build natural language context from discovery answers
            discovery_context = format_discovery_context(request.answers)

            # Get semantic candidates using RAG
            candidates = await self._get_semantic_candidates(
                discovery_context,
                max_candidates=self.settings.llm_scoring_max_candidates,
            )

            if not candidates:
                logger.warning("No semantic candidates found, falling back to manual")
                return await self._fallback_to_manual(request)

            # Score candidates with LLM
            scored_robots = await self._score_with_llm(
                discovery_context=discovery_context,
                candidates=candidates,
                session_id=session_id,
                profile_id=profile_id,
            )

            if not scored_robots:
                logger.warning("LLM scoring returned no results, falling back to manual")
                return await self._fallback_to_manual(request)

            # Build response
            response = await self._build_recommendations_response(
                scored_robots=scored_robots,
                candidates=candidates,
                request=request,
            )

            # Cache the response
            if use_cache:
                cache.set(request.answers, response)

            return response

        except TokenBudgetError:
            logger.warning("Token budget exceeded, falling back to manual scoring")
            raise  # Let the caller decide whether to fallback
        except OpenAIError as e:
            logger.error("OpenAI error in recommendations: %s", str(e))
            return await self._fallback_to_manual(request)
        except Exception as e:
            logger.error("Unexpected error in recommendations: %s", str(e))
            return await self._fallback_to_manual(request)

    async def _get_semantic_candidates(
        self,
        discovery_context: str,
        max_candidates: int = 8,
    ) -> list[dict[str, Any]]:
        """Get robot candidates using semantic search.

        Args:
            discovery_context: Natural language context from discovery.
            max_candidates: Maximum candidates to return.

        Returns:
            List of robot dictionaries with full data.
        """
        try:
            # Search using RAG
            search_results = await self.rag_service.search_robots_for_discovery(
                discovery_context=discovery_context,
                top_k=max_candidates,
            )

            if not search_results:
                # Fallback to all cleaning robots if RAG fails
                logger.warning("RAG search returned no results, using all robots")
                robots = await self.robot_catalog.list_robots(active_only=True)
                return robots[:max_candidates]

            # Get full robot data for the candidates
            robot_ids = [UUID(r["robot_id"]) for r in search_results if r.get("robot_id")]
            robots = await self.robot_catalog.get_robots_by_ids(robot_ids)

            # Add semantic scores to robot data
            score_map = {r["robot_id"]: r["semantic_score"] for r in search_results}
            for robot in robots:
                robot["_semantic_score"] = score_map.get(str(robot.get("id")), 0.5)

            return robots

        except Exception as e:
            logger.error("Error getting semantic candidates: %s", str(e))
            # Fallback to direct catalog query
            robots = await self.robot_catalog.list_robots(active_only=True)
            return robots[:max_candidates]

    async def _score_with_llm(
        self,
        discovery_context: str,
        candidates: list[dict[str, Any]],
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Score robot candidates using LLM.

        Args:
            discovery_context: Formatted discovery context.
            candidates: List of robot candidates.
            session_id: Optional session ID for budget tracking.
            profile_id: Optional profile ID for budget tracking.

        Returns:
            List of scored robots with match_score, label, summary, reasons.
        """
        # Build the prompt
        robots_context = format_robots_context(candidates)
        user_prompt = SCORING_USER_PROMPT_TEMPLATE.format(
            discovery_context=discovery_context,
            robots_context=robots_context,
        )

        # Check token budget
        budget_key: str | None = None
        is_authenticated = False
        if profile_id:
            budget_key = f"user:{profile_id}"
            is_authenticated = True
        elif session_id:
            budget_key = f"session:{session_id}"

        if budget_key:
            token_budget = get_token_budget()
            estimated_tokens = len(user_prompt) // 4 + 800  # Estimate
            allowed, remaining, limit = await token_budget.check_budget(
                budget_key, estimated_tokens, is_authenticated
            )
            if not allowed:
                raise TokenBudgetError(
                    message="Daily token budget exceeded for recommendations.",
                    tokens_used=limit - remaining,
                    daily_limit=limit,
                )

        # Call LLM
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=LLM_SCORING_SCHEMA,
                max_completion_tokens=1500,
                temperature=0.3,  # Lower temperature for more consistent scoring
            )

            # Track token usage
            if budget_key and response.usage:
                await token_budget.record_usage(budget_key, response.usage.total_tokens)
                logger.debug(
                    "Recommendation scoring used %d tokens",
                    response.usage.total_tokens,
                )

            # Parse response
            result = json.loads(response.choices[0].message.content or "{}")
            scored_robots = result.get("scored_robots", [])

            logger.info("LLM scored %d robots", len(scored_robots))
            return scored_robots

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM scoring response: %s", str(e))
            return []

    async def _build_recommendations_response(
        self,
        scored_robots: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        request: RecommendationsRequest,
    ) -> RecommendationsResponse:
        """Build the final recommendations response.

        Args:
            scored_robots: LLM-scored robots.
            candidates: Original robot candidate data.
            request: Original request.

        Returns:
            RecommendationsResponse.
        """
        from src.services.roi_service import ROIService

        roi_service = ROIService(robot_catalog_service=self.robot_catalog)

        # Create lookup maps
        candidate_map = {str(r.get("id")): r for r in candidates}
        score_map = {s["robot_id"]: s for s in scored_robots}

        # Get ROI inputs
        inputs = request.roi_inputs or roi_service.derive_roi_inputs(request.answers)

        # Sort scored robots by match_score
        sorted_scores = sorted(scored_robots, key=lambda x: x.get("match_score", 0), reverse=True)

        # Build recommendations
        recommendations: list[RobotRecommendation] = []
        other_options: list[OtherRobotOption] = []
        rank = 1

        for scored in sorted_scores:
            robot_id_str = scored.get("robot_id")
            robot = candidate_map.get(robot_id_str)

            if not robot:
                logger.warning("Robot ID %s from LLM not found in candidates", robot_id_str)
                continue

            try:
                robot_id = UUID(robot_id_str)
            except (ValueError, TypeError):
                logger.error("Invalid robot ID: %s", robot_id_str)
                continue

            # Calculate ROI
            roi = roi_service.calculate_roi(robot, inputs)

            # Parse image URLs
            raw_image_url = robot.get("image_url", "")
            image_urls = [url.strip() for url in raw_image_url.split(",") if url.strip()] if raw_image_url else []

            # Build reasons
            reasons = [
                RecommendationReason(
                    factor=r.get("factor", "Match"),
                    explanation=r.get("explanation", ""),
                    score_impact=r.get("score_impact", 0),
                )
                for r in scored.get("reasons", [])
            ]

            if rank <= request.top_k:
                recommendation = RobotRecommendation(
                    robot_id=robot_id,
                    robot_name=robot.get("name", "Unknown"),
                    vendor=robot.get("vendor", robot.get("manufacturer", "Unknown")),
                    category=robot.get("category", "Cleaning Robot"),
                    monthly_lease=float(robot.get("monthly_lease", 0)),
                    time_efficiency=float(robot.get("time_efficiency", 0.8)),
                    image_urls=image_urls,
                    rank=rank,
                    label=scored.get("label", "ALTERNATIVE"),
                    match_score=round(scored.get("match_score", 50), 1),
                    reasons=reasons,
                    summary=scored.get("summary", "A suitable option for your needs."),
                    projected_roi=roi,
                    modes=robot.get("modes", []),
                    surfaces=robot.get("surfaces", []),
                    key_reasons=robot.get("key_reasons", []),
                    specs=robot.get("specs", []),
                )
                recommendations.append(recommendation)
                rank += 1
            else:
                other_option = OtherRobotOption(
                    robot_id=robot_id,
                    robot_name=robot.get("name", "Unknown"),
                    vendor=robot.get("vendor", robot.get("manufacturer", "Unknown")),
                    category=robot.get("category", "Cleaning Robot"),
                    monthly_lease=float(robot.get("monthly_lease", 0)),
                    time_efficiency=float(robot.get("time_efficiency", 0.8)),
                    image_urls=image_urls,
                    match_score=round(scored.get("match_score", 50), 1),
                    modes=robot.get("modes", []),
                    surfaces=robot.get("surfaces", []),
                    key_reasons=robot.get("key_reasons", []),
                    specs=robot.get("specs", []),
                )
                other_options.append(other_option)

        return RecommendationsResponse(
            recommendations=recommendations,
            other_options=other_options,
            total_robots_evaluated=len(candidates),
            algorithm_version=LLM_ALGORITHM_VERSION,
            generated_at=datetime.utcnow(),
        )

    async def _fallback_to_manual(
        self,
        request: RecommendationsRequest,
    ) -> RecommendationsResponse:
        """Fallback to manual scoring algorithm.

        Args:
            request: Original recommendations request.

        Returns:
            RecommendationsResponse using manual scoring.
        """
        from src.services.roi_service import ROIService

        logger.info("Using manual scoring fallback")
        roi_service = ROIService(robot_catalog_service=self.robot_catalog)
        return await roi_service.get_recommendations_manual(request)


# Singleton instance
_recommendation_service: RecommendationService | None = None


def get_recommendation_service() -> RecommendationService:
    """Get or create the recommendation service singleton."""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService()
    return _recommendation_service
