"""Constants for profile extraction - mirrors frontend QUESTION_FLOW."""

from typing import Literal

# Answer groups for categorizing discovery questions
DiscoveryAnswerGroup = Literal["Company", "Facility", "Operations", "Economics", "Context"]

# Discovery questions mapped to keys, labels, and groups
# This should mirror the frontend QUESTION_FLOW for consistency
DISCOVERY_QUESTIONS = [
    {"id": 1, "key": "company_name", "label": "Company Name", "group": "Company"},
    {"id": 2, "key": "company_type", "label": "Company Type", "group": "Company"},
    {"id": 3, "key": "priorities", "label": "Top Priorities", "group": "Company"},
    {"id": 4, "key": "background", "label": "Facility Background", "group": "Facility"},
    {"id": 5, "key": "fnb", "label": "Food & Beverage", "group": "Facility"},
    {"id": 6, "key": "courts_count", "label": "Indoor Courts", "group": "Facility"},
    {"id": 7, "key": "surfaces", "label": "Surface Types", "group": "Facility"},
    {"id": 8, "key": "sqft", "label": "Total Sq Ft", "group": "Facility"},
    {"id": 9, "key": "method", "label": "Cleaning Method", "group": "Operations"},
    {"id": 10, "key": "responsibility", "label": "Responsibility", "group": "Operations"},
    {"id": 11, "key": "budget_exists", "label": "Budget Status", "group": "Economics"},
    {"id": 12, "key": "monthly_spend", "label": "Monthly Spend", "group": "Economics"},
    {"id": 13, "key": "frequency", "label": "Cleaning Frequency", "group": "Operations"},
    {"id": 14, "key": "timing", "label": "Cleaning Timing", "group": "Operations"},
    {"id": 15, "key": "duration", "label": "Session Duration", "group": "Operations"},
    {"id": 16, "key": "challenges", "label": "Pain Points", "group": "Operations"},
    {"id": 17, "key": "opportunity_cost", "label": "Opportunity Value", "group": "Economics"},
    {"id": 18, "key": "feedback", "label": "Member Feedback", "group": "Context"},
    {"id": 19, "key": "stakeholders", "label": "Stakeholders", "group": "Company"},
    {"id": 20, "key": "lifecycle", "label": "Resurfacing Timeline", "group": "Facility"},
    {"id": 21, "key": "failure_impact", "label": "Risk Impact", "group": "Operations"},
    {"id": 22, "key": "confidence", "label": "Confidence Score", "group": "Context"},
    {"id": 23, "key": "past_attempts", "label": "Past Experiments", "group": "Context"},
    {"id": 24, "key": "ideal_timeline", "label": "Ideal Timeline", "group": "Context"},
    {"id": 25, "key": "upcoming_events", "label": "Upcoming Events", "group": "Context"},
    {"id": 26, "key": "business_challenges", "label": "Business Constraints", "group": "Context"},
]

# Required questions for robot recommendation (must be gathered before ROI phase)
# These are the minimum questions needed to make an intelligent recommendation
REQUIRED_QUESTIONS = [
    {
        "key": "company_name",
        "question": "What is the name of your company?",
        "chips": None,  # Text input - no chips
    },
    {
        "key": "company_type",
        "question": "What type of company are we building this profile for?",
        "chips": ["Pickleball Club", "Tennis Club", "Restaurant", "Warehouse", "Datacenter"],
    },
    {
        "key": "courts_count",
        "question": "How many indoor courts do you have?",
        "chips": ["<4", "6", "8", "12+", "Other"],
    },
    {
        "key": "method",
        "question": "What is your primary cleaning method today?",
        "chips": ["Vacuum", "Sweep", "Mop", "Other"],
    },
    {
        "key": "duration",
        "question": "How long does it take to clean the whole facility?",
        "chips": ["1 hr", "2 hr", "4 hr", "Other"],
    },
    {
        "key": "monthly_spend",
        "question": "What is your estimated monthly cleaning spend?",
        "chips": ["<$2,000", "$2,000 - $5,000", "$5,000 - $10,000", "$10,000+"],
    },
]

# Required question keys for quick lookup
REQUIRED_QUESTION_KEYS = {q["key"] for q in REQUIRED_QUESTIONS}

# Create lookup by key for quick access
QUESTION_BY_KEY: dict[str, dict] = {q["key"]: q for q in DISCOVERY_QUESTIONS}

# All valid question keys
VALID_QUESTION_KEYS = set(QUESTION_BY_KEY.keys())

# System prompt for extraction
EXTRACTION_SYSTEM_PROMPT = """You are an extraction assistant for Autopilot, a robotics procurement platform.

Your task is to analyze the conversation and extract structured discovery data about the user's facility and needs.

IMPORTANT RULES:
1. Only extract information that was EXPLICITLY stated or strongly implied by the user
2. Do NOT infer or guess values - only extract what's clearly stated
3. If a value was mentioned earlier and not contradicted, keep it
4. Use the exact value provided by the user (e.g., "50000 sqft", not "50,000 square feet")
5. For ROI inputs, only extract when specific numbers are mentioned
6. Return an empty answers object {} if no extractable data is found

CRITICAL: Company Name vs Company Type Distinction
- company_name: The actual business/organization name (e.g., "Downtown Pickleball Club", "Smith's Tennis Center", "Joe's Restaurant", "ABC Warehouse"). This is a specific, unique name for the business.
- company_type: The category/type of business from: "Pickleball Club", "Tennis Club", "Restaurant", "Warehouse", "Datacenter". This is the general industry category, NOT the specific business name.
- If the user says only "Pickleball Club" without a specific name, extract it as company_type ONLY, not as company_name.
- If the user provides a specific business name (e.g., "Downtown Pickleball Club"), extract "Downtown Pickleball Club" as company_name and "Pickleball Club" as company_type.

The discovery questions cover these groups:
- Company: company_name, company_type, priorities, stakeholders
- Facility: background, fnb (food & beverage), courts_count, surfaces, sqft, lifecycle
- Operations: method (cleaning), responsibility, frequency, timing, duration, challenges, failure_impact
- Economics: budget_exists, monthly_spend, opportunity_cost
- Context: feedback, confidence, past_attempts, ideal_timeline, upcoming_events, business_challenges

Extract ROI inputs when the user mentions:
- laborRate: hourly wages or labor costs per hour
- manualMonthlySpend: current monthly cleaning costs or budget
- manualMonthlyHours: hours spent on cleaning per month"""

EXTRACTION_USER_PROMPT = """Analyze this conversation and extract any discovery profile data mentioned by the user.

Current extracted data (preserve unless contradicted):
{current_answers}

Recent conversation:
{conversation_messages}

Extract only NEW or UPDATED information from the user's messages. Return each extracted item in the answers array with all required fields (questionId, key, label, value, group). If no new extractable data is found, return an empty answers array []."""

# All valid question keys as enum for strict schema validation
VALID_QUESTION_KEYS_ENUM = [q["key"] for q in DISCOVERY_QUESTIONS]

# All valid groups
VALID_GROUPS_ENUM = ["Company", "Facility", "Operations", "Economics", "Context"]

# JSON Schema for structured output - uses array with enum keys for strict mode compatibility
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "description": "Discovery answers extracted from conversation",
            "items": {
                "type": "object",
                "properties": {
                    "questionId": {
                        "type": "integer",
                        "description": "Question ID (1-26)"
                    },
                    "key": {
                        "type": "string",
                        "enum": VALID_QUESTION_KEYS_ENUM,
                        "description": "Question key identifier"
                    },
                    "label": {
                        "type": "string",
                        "description": "Human-readable label"
                    },
                    "value": {
                        "type": "string",
                        "description": "Extracted value from user"
                    },
                    "group": {
                        "type": "string",
                        "enum": VALID_GROUPS_ENUM,
                        "description": "Question category"
                    }
                },
                "required": ["questionId", "key", "label", "value", "group"],
                "additionalProperties": False
            }
        },
        "roi_inputs": {
            "type": "object",
            "description": "ROI calculation inputs if mentioned (use null for unknown values)",
            "properties": {
                "laborRate": {
                    "type": ["number", "null"],
                    "description": "Hourly labor rate in dollars, or null if not mentioned"
                },
                "manualMonthlySpend": {
                    "type": ["number", "null"],
                    "description": "Monthly cleaning spend in dollars, or null if not mentioned"
                },
                "manualMonthlyHours": {
                    "type": ["number", "null"],
                    "description": "Monthly hours spent on cleaning, or null if not mentioned"
                }
            },
            "required": ["laborRate", "manualMonthlySpend", "manualMonthlyHours"],
            "additionalProperties": False
        },
        "extraction_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence in the extraction accuracy"
        }
    },
    "required": ["answers", "roi_inputs", "extraction_confidence"],
    "additionalProperties": False
}
