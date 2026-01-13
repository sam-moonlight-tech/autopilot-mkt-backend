"""LLM prompts and schemas for intelligent robot recommendations."""

# System prompt for robot scoring
SCORING_SYSTEM_PROMPT = """You are an expert robotics procurement consultant specializing in commercial cleaning robots.

Your task is to score and rank robots for a customer based on their specific needs.

SCORING CRITERIA (total 100 points):
1. Facility Type Match (0-30): How well the robot's capabilities match the facility type
   - Court-specialized robots for sports facilities
   - Compact robots for restaurants/retail
   - Industrial robots for warehouses/datacenters

2. Cleaning Method Compatibility (0-25): Match between robot modes and required cleaning methods
   - Vacuum, mop, scrub, sweep capabilities
   - Multi-mode robots score higher for versatile needs

3. Budget Alignment (0-20): How well the robot cost fits the customer's budget
   - Robot cost ≤ 50% of budget = full points
   - Robot cost ≤ budget = good score
   - Robot cost > 150% of budget = minimal points

4. Operational Efficiency (0-15): Time savings and efficiency gains
   - Higher time_efficiency ratings score better
   - Coverage rates and automation level

5. Unique Value Factors (0-10): Special features that address specific pain points
   - Surface compatibility
   - Size/maneuverability for the space
   - Special features relevant to the use case

GUIDELINES:
- Be specific about WHY features matter for THIS customer's situation
- Higher scores = better match, not just more expensive
- Consider the customer's stated priorities
- A perfect match should score 85-95, not always 100
- Differentiate robots clearly - avoid giving everyone similar scores"""

# User prompt template
SCORING_USER_PROMPT_TEMPLATE = """CUSTOMER PROFILE:
{discovery_context}

CANDIDATE ROBOTS TO EVALUATE:
{robots_context}

Score each robot based on how well it matches this customer's specific needs. Provide detailed reasoning.

Return a JSON object with scored_robots array."""

# Structured output schema for LLM scoring
LLM_SCORING_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "robot_scores",
        "schema": {
            "type": "object",
            "properties": {
                "scored_robots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "robot_id": {
                                "type": "string",
                                "description": "UUID of the robot being scored"
                            },
                            "match_score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Overall match score (0-100)"
                            },
                            "label": {
                                "type": "string",
                                "enum": ["RECOMMENDED", "BEST VALUE", "UPGRADE", "ALTERNATIVE"],
                                "description": "Display label for this recommendation"
                            },
                            "summary": {
                                "type": "string",
                                "description": "One sentence explaining why this robot is recommended for this customer"
                            },
                            "reasons": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "factor": {
                                            "type": "string",
                                            "description": "The scoring factor (e.g., 'Facility Match', 'Budget Fit')"
                                        },
                                        "explanation": {
                                            "type": "string",
                                            "description": "Why this factor matters for this customer"
                                        },
                                        "score_impact": {
                                            "type": "number",
                                            "description": "Points contributed by this factor"
                                        }
                                    },
                                    "required": ["factor", "explanation", "score_impact"],
                                    "additionalProperties": False
                                },
                                "minItems": 2,
                                "maxItems": 4,
                                "description": "Reasons for this score"
                            }
                        },
                        "required": ["robot_id", "match_score", "label", "summary", "reasons"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["scored_robots"],
            "additionalProperties": False
        },
        "strict": True
    }
}


def format_discovery_context(answers: dict) -> str:
    """Format discovery answers into natural language context for LLM.

    Args:
        answers: Dictionary of discovery answers.

    Returns:
        Formatted context string.
    """
    lines = []

    # Company/Facility type
    company_type = _get_answer_value(answers, "company_type")
    if company_type:
        lines.append(f"- Facility Type: {company_type}")

    # Company name
    company_name = _get_answer_value(answers, "company_name")
    if company_name:
        lines.append(f"- Company: {company_name}")

    # Size/Courts
    courts_count = _get_answer_value(answers, "courts_count")
    if courts_count:
        lines.append(f"- Size: {courts_count} courts/areas")

    # Cleaning method
    method = _get_answer_value(answers, "method")
    if method:
        lines.append(f"- Primary Cleaning Method Needed: {method}")

    # Duration/Time
    duration = _get_answer_value(answers, "duration")
    if duration:
        lines.append(f"- Daily Cleaning Duration: {duration}")

    # Budget
    monthly_spend = _get_answer_value(answers, "monthly_spend")
    if monthly_spend:
        lines.append(f"- Current Monthly Cleaning Budget: {monthly_spend}")

    # Add any additional context from other answers
    for key, answer in answers.items():
        if key not in ["company_type", "company_name", "courts_count", "method", "duration", "monthly_spend"]:
            value = _get_answer_value(answers, key)
            if value:
                # Convert key to readable label
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {value}")

    return "\n".join(lines) if lines else "No specific requirements provided."


def format_robots_context(robots: list[dict]) -> str:
    """Format robot catalog data for LLM scoring context.

    Args:
        robots: List of robot dictionaries from catalog.

    Returns:
        Formatted robots context string.
    """
    lines = []

    for i, robot in enumerate(robots, 1):
        robot_id = str(robot.get("id", "unknown"))
        name = robot.get("name", "Unknown Robot")
        category = robot.get("category", "Robot")
        best_for = robot.get("best_for", "general use")
        modes = robot.get("modes", [])
        surfaces = robot.get("surfaces", [])
        monthly_lease = robot.get("monthly_lease", 0)
        time_efficiency = robot.get("time_efficiency", 0.8)
        key_reasons = robot.get("key_reasons", [])

        lines.append(f"\n{i}. {name} (ID: {robot_id})")
        lines.append(f"   Category: {category}")
        lines.append(f"   Best For: {best_for}")
        lines.append(f"   Cleaning Modes: {', '.join(modes) if modes else 'N/A'}")
        lines.append(f"   Supported Surfaces: {', '.join(surfaces) if surfaces else 'All surfaces'}")
        lines.append(f"   Monthly Lease: ${float(monthly_lease):,.0f}")
        lines.append(f"   Time Efficiency: {float(time_efficiency) * 100:.0f}%")
        if key_reasons:
            lines.append(f"   Key Features: {'; '.join(key_reasons[:3])}")

    return "\n".join(lines)


def _get_answer_value(answers: dict, key: str) -> str | None:
    """Safely extract value from a discovery answer.

    Args:
        answers: Dictionary of answers.
        key: Answer key to extract.

    Returns:
        The value string or None.
    """
    answer = answers.get(key)
    if answer is None:
        return None
    if isinstance(answer, dict):
        return str(answer.get("value", ""))
    return str(answer) if answer else None
