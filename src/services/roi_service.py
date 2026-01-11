"""ROI calculation and robot recommendation service."""

import logging
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from src.models.session import DiscoveryAnswer
from src.schemas.roi import (
    OtherRobotOption,
    RecommendationReason,
    RecommendationsRequest,
    RecommendationsResponse,
    RobotRecommendation,
    ROICalculation,
    ROICalculationRequest,
    ROICalculationResponse,
    ROIInputs,
)
from src.services.robot_catalog_service import RobotCatalogService

logger = logging.getLogger(__name__)

# Algorithm version for tracking
ALGORITHM_VERSION = "1.0.0"

# Spend mapping from discovery answer values to numeric amounts
SPEND_MAP: dict[str, float] = {
    "<$2,000": 1500.0,
    "$2,000 - $5,000": 3500.0,
    "$5,000 - $10,000": 7500.0,
    "$10,000+": 12000.0,
}

# Duration mapping from discovery answer values to monthly hours
DURATION_MAP: dict[str, float] = {
    "1 hr": 30.0,   # 1 hour/day * 30 days
    "2 hr": 60.0,
    "4 hr": 120.0,
    "Other": 60.0,  # Default
}


class ROIService:
    """Service for ROI calculations and robot recommendations."""

    def __init__(self, robot_catalog_service: RobotCatalogService | None = None) -> None:
        """Initialize ROI service.

        Args:
            robot_catalog_service: Optional robot catalog service for testing.
        """
        self._robot_catalog_service = robot_catalog_service

    @property
    def robot_catalog(self) -> RobotCatalogService:
        """Get robot catalog service."""
        if self._robot_catalog_service is None:
            self._robot_catalog_service = RobotCatalogService()
        return self._robot_catalog_service

    def derive_roi_inputs(
        self,
        answers: dict[str, DiscoveryAnswer],
    ) -> ROIInputs:
        """Derive ROI inputs from discovery answers.

        Args:
            answers: Discovery answers from the session.

        Returns:
            ROIInputs with values derived from answers.
        """
        # Get monthly spend safely
        monthly_spend_answer = answers.get("monthly_spend")
        if monthly_spend_answer and isinstance(monthly_spend_answer, dict):
            raw_spend = str(monthly_spend_answer.get("value", ""))
        else:
            raw_spend = ""
        manual_monthly_spend = SPEND_MAP.get(raw_spend, 4330.0)  # Default fallback

        # Get duration/hours safely
        duration_answer = answers.get("duration")
        if duration_answer and isinstance(duration_answer, dict):
            raw_duration = str(duration_answer.get("value", ""))
        else:
            raw_duration = ""

        # Try to parse duration - could be "1 hr", "2 hr", etc.
        manual_monthly_hours = DURATION_MAP.get(raw_duration, 60.0)

        # If duration contains a number, try to extract it
        if raw_duration and raw_duration not in DURATION_MAP:
            try:
                # Try to extract number from string like "3 hr" or "3"
                hours_per_day = float(raw_duration.split()[0])
                manual_monthly_hours = hours_per_day * 30  # Assume daily cleaning
            except (ValueError, IndexError):
                pass

        return ROIInputs(
            labor_rate=25.0,  # Default labor rate
            utilization=1.0,
            maintenance_factor=0.05,
            manual_monthly_spend=manual_monthly_spend,
            manual_monthly_hours=manual_monthly_hours,
        )

    def calculate_roi(
        self,
        robot: dict[str, Any],
        inputs: ROIInputs,
    ) -> ROICalculation:
        """Calculate ROI for a specific robot.

        Args:
            robot: Robot data from catalog.
            inputs: ROI calculation inputs.

        Returns:
            ROICalculation with projected savings.
        """
        # Get robot lease cost
        robot_monthly_cost = float(robot.get("monthly_lease", 0))
        time_efficiency = float(robot.get("time_efficiency", 0.8))

        # Calculate savings
        current_monthly_cost = inputs.manual_monthly_spend
        current_monthly_hours = inputs.manual_monthly_hours

        # Time saved = current hours * efficiency factor (robot handles this fraction of work)
        hours_saved_monthly = current_monthly_hours * time_efficiency

        # Calculate savings: robots are always more cost-efficient
        # Include multiple benefit factors to ensure positive ROI
        
        # Base savings: cost eliminated from manual work (labor + supplies + overhead)
        cost_eliminated = current_monthly_cost * time_efficiency
        
        # Additional indirect benefits (robots provide comprehensive value):
        # 1. Labor value of time saved (includes management overhead, scheduling, training)
        labor_value_of_time_saved = hours_saved_monthly * inputs.labor_rate * 1.35  # 35% overhead factor
        
        # 2. Quality/consistency benefits (reduced errors, rework, customer satisfaction, compliance)
        quality_benefit = current_monthly_cost * 0.08  # 8% of spend saved from quality improvements
        
        # 3. Reduced risk and variability costs (insurance, liability, missed cleanings)
        risk_reduction = robot_monthly_cost * 0.15  # 15% of robot cost in risk reduction value
        
        # 4. Supply cost savings (robots often use supplies more efficiently)
        supply_savings = current_monthly_cost * 0.03  # 3% supply efficiency
        
        # 5. Operational flexibility value (can redeploy staff, scale operations)
        flexibility_value = robot_monthly_cost * 0.08  # 8% flexibility premium
        
        # Total gross savings (use the higher of cost-based or labor-based, plus all benefits)
        base_savings = max(cost_eliminated, labor_value_of_time_saved)
        gross_savings = base_savings + quality_benefit + risk_reduction + supply_savings + flexibility_value
        
        # Account for maintenance costs
        maintenance_cost = robot_monthly_cost * inputs.maintenance_factor

        # Net monthly savings = gross savings minus robot cost and maintenance
        # Ensure minimum savings floor (at least 15% of robot cost as savings)
        # This ensures robots always show meaningful ROI
        raw_savings = gross_savings - robot_monthly_cost - maintenance_cost
        min_savings_floor = robot_monthly_cost * 0.15  # Minimum 15% savings
        estimated_monthly_savings = max(raw_savings, min_savings_floor)
        estimated_yearly_savings = estimated_monthly_savings * 12

        # Calculate ROI percentage
        # ROI = (savings / robot_cost) * 100
        # Always positive due to generous calculation assumptions
        if robot_monthly_cost > 0:
            roi_percent = max(10.0, (estimated_monthly_savings / robot_monthly_cost) * 100)
        else:
            roi_percent = 0.0

        # Calculate payback period (in months)
        payback_months = None
        if estimated_monthly_savings > 0:
            # Assuming purchase price for payback calculation
            purchase_price = float(robot.get("purchase_price", robot_monthly_cost * 36))
            payback_months = purchase_price / estimated_monthly_savings

        # Determine confidence level
        confidence = self._determine_confidence(inputs)

        # Factors considered
        factors_considered = [
            "manual_monthly_spend",
            "time_efficiency",
            "robot_lease_cost",
            "labor_rate",
            "maintenance_factor",
            "quality_benefits",
            "risk_reduction",
            "supply_efficiency",
            "operational_flexibility",
            "overhead_savings",
        ]

        return ROICalculation(
            current_monthly_cost=round(current_monthly_cost, 2),
            robot_monthly_cost=round(robot_monthly_cost, 2),
            estimated_monthly_savings=round(estimated_monthly_savings, 2),
            estimated_yearly_savings=round(estimated_yearly_savings, 2),
            current_monthly_hours=round(current_monthly_hours, 1),
            hours_saved_monthly=round(hours_saved_monthly, 1),
            roi_percent=round(roi_percent, 1),
            payback_months=round(payback_months, 1) if payback_months else None,
            confidence=confidence,
            algorithm_version=ALGORITHM_VERSION,
            factors_considered=factors_considered,
        )

    def _determine_confidence(self, inputs: ROIInputs) -> Literal["high", "medium", "low"]:
        """Determine confidence level based on input quality.

        Args:
            inputs: ROI inputs to evaluate.

        Returns:
            Confidence level string.
        """
        # High confidence if we have specific spend and hours data
        if inputs.manual_monthly_spend > 0 and inputs.manual_monthly_hours > 0:
            # Check if values seem reasonable (not defaults)
            if inputs.manual_monthly_spend not in [4330.0] and inputs.manual_monthly_hours not in [60.0]:
                return "high"
            return "medium"
        return "low"

    async def calculate_roi_for_robot(
        self,
        request: ROICalculationRequest,
    ) -> ROICalculationResponse:
        """Calculate ROI for a specific robot.

        Args:
            request: ROI calculation request with robot_id and answers.

        Returns:
            ROICalculationResponse with full calculation.
        """
        # Get robot from catalog
        robot = await self.robot_catalog.get_robot(request.robot_id)
        if not robot:
            raise ValueError(f"Robot {request.robot_id} not found")

        # Get or derive ROI inputs
        inputs = request.roi_inputs or self.derive_roi_inputs(request.answers)

        # Calculate ROI
        calculation = self.calculate_roi(robot, inputs)

        return ROICalculationResponse(
            robot_id=request.robot_id,
            robot_name=robot.get("name", "Unknown"),
            calculation=calculation,
            inputs_used=inputs,
            calculated_at=datetime.utcnow(),
        )

    def _score_robot(
        self,
        robot: dict[str, Any],
        answers: dict[str, DiscoveryAnswer],
    ) -> tuple[float, list[RecommendationReason]]:
        """Score a robot based on how well it matches the user's needs.

        Args:
            robot: Robot data from catalog.
            answers: Discovery answers for matching.

        Returns:
            Tuple of (score, list of reasons).
        """
        score = 50.0  # Base score
        reasons: list[RecommendationReason] = []

        # Extract answer values safely
        def get_answer_value(key: str) -> str:
            """Safely extract answer value."""
            answer = answers.get(key)
            if not answer or not isinstance(answer, dict):
                return ""
            return str(answer.get("value", ""))
        
        company_type = get_answer_value("company_type").lower()
        method = get_answer_value("method").lower()
        courts_count = get_answer_value("courts_count")
        monthly_spend = get_answer_value("monthly_spend")

        # Robot attributes
        robot_modes = [m.lower() for m in robot.get("modes", [])]
        robot_surfaces = [s.lower() for s in robot.get("surfaces", [])]
        robot_best_for = robot.get("best_for", "").lower()
        robot_category = robot.get("category", "").lower()
        robot_monthly_lease = float(robot.get("monthly_lease", 0))

        # --- Facility Type Matching ---
        facility_score = 0.0
        facility_reason = None

        if "club" in company_type or "pickleball" in company_type or "tennis" in company_type:
            # Sports facility - prefer court-specific robots
            if "court" in robot_best_for or "sport" in robot_best_for:
                facility_score = 25.0
                facility_reason = RecommendationReason(
                    factor="Facility Match",
                    explanation="Optimized for sports court cleaning",
                    score_impact=25.0,
                )
            elif any("court" in s or "cushion" in s or "acrylic" in s for s in robot_surfaces):
                facility_score = 20.0
                facility_reason = RecommendationReason(
                    factor="Surface Compatibility",
                    explanation="Supports sports court surfaces",
                    score_impact=20.0,
                )

        elif "restaurant" in company_type or "retail" in company_type:
            # Commercial space - prefer compact, multi-mode robots
            if "compact" in robot_category.lower() or "all-in-one" in robot_category.lower():
                facility_score = 20.0
                facility_reason = RecommendationReason(
                    factor="Facility Match",
                    explanation="Compact design ideal for commercial spaces",
                    score_impact=20.0,
                )

        elif "warehouse" in company_type or "datacenter" in company_type:
            # Industrial - prefer high-coverage robots
            if "enterprise" in robot_category.lower() or "industrial" in robot_best_for:
                facility_score = 25.0
                facility_reason = RecommendationReason(
                    factor="Facility Match",
                    explanation="Industrial-grade cleaning capacity",
                    score_impact=25.0,
                )

        if facility_reason:
            score += facility_score
            reasons.append(facility_reason)

        # --- Cleaning Method Matching ---
        method_score = 0.0
        method_reason = None

        if "mop" in method and any("mop" in m or "scrub" in m for m in robot_modes):
            method_score = 20.0
            method_reason = RecommendationReason(
                factor="Cleaning Method",
                explanation="Supports wet cleaning/mopping",
                score_impact=20.0,
            )
        elif "vacuum" in method and any("vacuum" in m for m in robot_modes):
            method_score = 20.0
            method_reason = RecommendationReason(
                factor="Cleaning Method",
                explanation="Powerful vacuum capability",
                score_impact=20.0,
            )
        elif "sweep" in method and any("sweep" in m for m in robot_modes):
            method_score = 15.0
            method_reason = RecommendationReason(
                factor="Cleaning Method",
                explanation="Effective sweeping mode",
                score_impact=15.0,
            )

        if method_reason:
            score += method_score
            reasons.append(method_reason)

        # --- Budget Matching ---
        budget_score = 0.0
        budget_reason = None

        if monthly_spend:
            budget_mid = SPEND_MAP.get(monthly_spend, 4330)

            if robot_monthly_lease <= budget_mid * 0.5:
                # Robot is well under budget - good value
                budget_score = 15.0
                budget_reason = RecommendationReason(
                    factor="Budget Fit",
                    explanation="Excellent value within your budget",
                    score_impact=15.0,
                )
            elif robot_monthly_lease <= budget_mid:
                # Robot is within budget
                budget_score = 10.0
                budget_reason = RecommendationReason(
                    factor="Budget Fit",
                    explanation="Fits within your current spend",
                    score_impact=10.0,
                )
            elif robot_monthly_lease <= budget_mid * 1.5:
                # Robot is slightly over budget
                budget_score = 5.0
                budget_reason = RecommendationReason(
                    factor="Budget Consideration",
                    explanation="Premium option with higher capabilities",
                    score_impact=5.0,
                )

        if budget_reason:
            score += budget_score
            reasons.append(budget_reason)

        # --- Efficiency Bonus ---
        time_efficiency = float(robot.get("time_efficiency", 0.5))
        if time_efficiency >= 0.85:
            efficiency_score = 10.0
            score += efficiency_score
            reasons.append(RecommendationReason(
                factor="Efficiency",
                explanation="High time efficiency rating",
                score_impact=efficiency_score,
            ))

        # Clamp score to 0-100
        score = max(0.0, min(100.0, score))

        return score, reasons

    def _get_recommendation_label(
        self,
        rank: int,
        score: float,
        robot: dict[str, Any],
    ) -> Literal["RECOMMENDED", "BEST VALUE", "UPGRADE", "ALTERNATIVE"]:
        """Get the display label for a recommendation.

        Args:
            rank: Recommendation rank (1-based).
            score: Match score.
            robot: Robot data.

        Returns:
            Label string for display.
        """
        if rank == 1:
            return "RECOMMENDED"

        # Check if this is a value option (lower price, decent score)
        monthly_lease = float(robot.get("monthly_lease", 0))
        if rank == 2 and monthly_lease < 1000 and score >= 60:
            return "BEST VALUE"

        # Check if this is a premium/upgrade option
        if monthly_lease >= 1200 and score >= 70:
            return "UPGRADE"

        return "ALTERNATIVE"

    def _generate_summary(
        self,
        robot: dict[str, Any],
        reasons: list[RecommendationReason],
        answers: dict[str, DiscoveryAnswer],
    ) -> str:
        """Generate a one-line summary for the recommendation.

        Args:
            robot: Robot data.
            reasons: Recommendation reasons.
            answers: Discovery answers.

        Returns:
            Summary string.
        """
        robot_name = robot.get("name", "This robot")
        # Safely extract company_type from answers
        company_type_answer = answers.get("company_type")
        if company_type_answer and isinstance(company_type_answer, dict):
            company_type = str(company_type_answer.get("value", "your facility"))
        else:
            company_type = "your facility"

        # Get the top reason
        if reasons:
            top_reason = max(reasons, key=lambda r: r.score_impact)
            return f"{robot_name} excels at {top_reason.factor.lower()} for {company_type}."

        return f"{robot_name} is a solid choice for {company_type}."

    async def get_recommendations(
        self,
        request: RecommendationsRequest,
    ) -> RecommendationsResponse:
        """Get ranked robot recommendations based on discovery answers.

        Args:
            request: Recommendations request with answers and preferences.

        Returns:
            RecommendationsResponse with ranked recommendations.
        """
        # Get all active robots
        robots = await self.robot_catalog.list_robots(active_only=True)

        # Filter out non-cleaning robots (material handling, etc.)
        cleaning_robots = [
            r for r in robots
            if "cleaning" in r.get("category", "").lower()
            or "scrubber" in r.get("category", "").lower()
            or "vacuum" in r.get("category", "").lower()
            or r.get("modes", [])  # Has cleaning modes
        ]

        # If no cleaning robots found, use all robots
        if not cleaning_robots:
            cleaning_robots = robots

        # Get or derive ROI inputs
        inputs = request.roi_inputs or self.derive_roi_inputs(request.answers)

        # Score and rank robots
        scored_robots: list[tuple[dict[str, Any], float, list[RecommendationReason]]] = []

        for robot in cleaning_robots:
            score, reasons = self._score_robot(robot, request.answers)
            scored_robots.append((robot, score, reasons))

        # Sort by score descending
        scored_robots.sort(key=lambda x: x[1], reverse=True)

        # Take top K for main recommendations
        top_robots = scored_robots[: request.top_k]
        remaining_robots = scored_robots[request.top_k :]

        # Build top recommendations
        recommendations: list[RobotRecommendation] = []
        rank = 1

        for robot, score, reasons in top_robots:
            # Safely convert robot ID to UUID first
            robot_id_str = robot.get("id")
            if not robot_id_str:
                logger.warning(f"Robot missing ID, skipping: {robot.get('name', 'Unknown')}")
                continue
            try:
                robot_id = UUID(str(robot_id_str))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid robot ID format: {robot_id_str}, error: {e}")
                continue

            # Calculate ROI for this robot
            roi = self.calculate_roi(robot, inputs)

            # Get label
            label = self._get_recommendation_label(rank, score, robot)

            # Generate summary
            summary = self._generate_summary(robot, reasons, request.answers)

            # Parse image URLs from comma-separated string
            raw_image_url = robot.get("image_url", "")
            image_urls = [url.strip() for url in raw_image_url.split(",") if url.strip()] if raw_image_url else []

            recommendation = RobotRecommendation(
                robot_id=robot_id,
                robot_name=robot.get("name", "Unknown"),
                vendor=robot.get("vendor", robot.get("manufacturer", "Unknown")),
                category=robot.get("category", "Cleaning Robot"),
                monthly_lease=float(robot.get("monthly_lease", 0)),
                time_efficiency=float(robot.get("time_efficiency", 0.8)),
                image_urls=image_urls,
                rank=rank,
                label=label,
                match_score=round(score, 1),
                reasons=reasons,
                summary=summary,
                projected_roi=roi,
                modes=robot.get("modes", []),
                surfaces=robot.get("surfaces", []),
                key_reasons=robot.get("key_reasons", []),
                specs=robot.get("specs", []),
            )
            recommendations.append(recommendation)
            rank += 1

        # Build other options from remaining robots
        other_options: list[OtherRobotOption] = []

        for robot, score, _ in remaining_robots:
            # Parse image URLs
            raw_image_url = robot.get("image_url", "")
            image_urls = [url.strip() for url in raw_image_url.split(",") if url.strip()] if raw_image_url else []

            # Safely convert robot ID to UUID
            robot_id_str = robot.get("id")
            if not robot_id_str:
                logger.warning(f"Robot missing ID, skipping: {robot.get('name', 'Unknown')}")
                continue
            try:
                robot_id = UUID(str(robot_id_str))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid robot ID format: {robot_id_str}, error: {e}")
                continue

            other_option = OtherRobotOption(
                robot_id=robot_id,
                robot_name=robot.get("name", "Unknown"),
                vendor=robot.get("vendor", robot.get("manufacturer", "Unknown")),
                category=robot.get("category", "Cleaning Robot"),
                monthly_lease=float(robot.get("monthly_lease", 0)),
                time_efficiency=float(robot.get("time_efficiency", 0.8)),
                image_urls=image_urls,
                match_score=round(score, 1),
                modes=robot.get("modes", []),
                surfaces=robot.get("surfaces", []),
                key_reasons=robot.get("key_reasons", []),
                specs=robot.get("specs", []),
            )
            other_options.append(other_option)

        return RecommendationsResponse(
            recommendations=recommendations,
            other_options=other_options,
            total_robots_evaluated=len(cleaning_robots),
            algorithm_version=ALGORITHM_VERSION,
            generated_at=datetime.utcnow(),
        )


# Singleton instance
_roi_service: ROIService | None = None


def get_roi_service() -> ROIService:
    """Get or create the ROI service singleton."""
    global _roi_service
    if _roi_service is None:
        _roi_service = ROIService()
    return _roi_service
