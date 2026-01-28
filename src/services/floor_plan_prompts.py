"""GPT-4o Vision prompts and JSON schema for floor plan analysis."""

# System prompt for floor plan analysis
FLOOR_PLAN_ANALYSIS_SYSTEM_PROMPT = """You are an expert facility analyst specializing in sports venues and commercial floor plan analysis for robotic cleaning automation.

Your task is to analyze a floor plan image of a sports facility (typically pickleball or tennis courts) and extract structured data about the layout for robotic cleaning cost estimation.

ANALYSIS GUIDELINES:

1. COURT IDENTIFICATION:
   - Look for labeled courts (e.g., "Court 1", "Court 2", etc.)
   - Courts are typically outlined with red or bold lines in architectural drawings
   - Standard pickleball court: 44' x 20' (880 sq ft playing area)
   - Standard tennis court: 78' x 36' (2,808 sq ft)
   - Note max occupancy labels if visible (e.g., "MAX OCC 4")
   - Identify net positions (these are virtual boundaries for robots)

2. ZONE CLASSIFICATION:
   - COURT ZONES: Playing surfaces, typically acrylic sport court material
   - CIRCULATION ZONES: Walkways, spectator areas, often shown with hex-textured pattern
   - BUFFER ZONES: Spacing between courts (typically 5-10 ft), treated as circulation
   - AUXILIARY ZONES: Pro shops, offices, lobby areas - cleanable by robots
   - EXCLUDED ZONES: Restrooms (manual only), mechanical rooms, storage

3. DIMENSION EXTRACTION:
   - Look for dimension annotations on the floor plan (e.g., "68'-7"", "20'-0"")
   - Extract overall facility dimensions from perimeter annotations
   - Extract individual court dimensions if annotated
   - Note buffer zone widths between courts (typically 5'-0" to 10'-0")
   - Calculate total square footage per zone

4. SURFACE IDENTIFICATION:
   - Sport court surfaces: Look for court markings, painted lines, acrylic indicators
   - Rubber tile: Often shown with hexagonal or honeycomb texture pattern in drawings
   - Modular flooring: Interlocking tile patterns
   - Concrete: Usually service areas, back-of-house

5. OBSTRUCTIONS:
   - Nets: Mark as virtual boundaries (robot navigates around during play)
   - Benches/seating: No-go zones or navigate-around depending on size
   - Posts/columns: Navigate around
   - Equipment storage areas

6. CONFIDENCE SCORING:
   - HIGH (0.85-1.0): Clear labels, visible dimensions, obvious features
   - MEDIUM (0.6-0.84): Partial labels, estimated dimensions from context
   - LOW (0.3-0.59): Inferred from context, unclear markings
   - If you cannot determine something, use LOW confidence and note in extraction_notes

IMPORTANT:
- If dimensions are not labeled, estimate based on standard court sizes and provide LOW confidence
- Always err on the side of LOWER confidence if uncertain
- Restrooms are ALWAYS excluded from robot cleaning (manual cleaning only)
- Mechanical/utility rooms are ALWAYS excluded
- Buffer zones between courts follow CIRCULATION cleaning schedule, not court schedule
- The hexagonal pattern in drawings typically indicates rubber tile flooring (circulation areas)"""

# User prompt template
FLOOR_PLAN_ANALYSIS_USER_PROMPT = """Analyze this floor plan image and extract all relevant features for robotic cleaning cost estimation.

Focus on:
1. Total facility dimensions and layout
2. Individual court identification and dimensions (look for "Court N" labels)
3. Buffer zones between courts (5-10 ft spacing areas)
4. Circulation areas (walkways, spectator areas - often shown with hex texture)
5. Auxiliary spaces (pro shop, office, lobby)
6. Areas to exclude from robotic cleaning (restrooms, mechanical rooms)
7. Obstructions that affect robot navigation (nets, benches, posts)

Provide confidence scores for each extracted feature based on image clarity and labeling.

Return the analysis in the specified JSON format."""

# Valid enum values for strict schema
SURFACE_TYPES = ["sport_court_acrylic", "rubber_tile", "modular", "concrete", "other"]
EXCLUSION_REASONS = ["manual_only", "access_restricted", "hazardous"]
OBSTRUCTION_TYPES = ["net", "bench", "post", "equipment", "other"]
OBSTRUCTION_HANDLING = ["virtual_boundary", "no_go_zone", "navigate_around"]

# JSON Schema for structured output - compatible with OpenAI's strict mode
FLOOR_PLAN_EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "floor_plan_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "facility_dimensions": {
                    "type": "object",
                    "description": "Overall facility dimensions",
                    "properties": {
                        "length_ft": {"type": "number", "description": "Facility length in feet"},
                        "width_ft": {"type": "number", "description": "Facility width in feet"},
                        "total_sqft": {"type": "number", "description": "Total square footage"},
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1",
                        },
                    },
                    "required": ["length_ft", "width_ft", "total_sqft", "confidence"],
                    "additionalProperties": False,
                },
                "courts": {
                    "type": "array",
                    "description": "List of detected courts",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Court label (e.g., 'Court 1')"},
                            "length_ft": {"type": "number", "description": "Court length in feet"},
                            "width_ft": {"type": "number", "description": "Court width in feet"},
                            "sqft": {"type": "number", "description": "Court square footage"},
                            "surface_type": {
                                "type": "string",
                                "enum": SURFACE_TYPES,
                                "description": "Surface material type",
                            },
                            "max_occupancy": {
                                "type": ["integer", "null"],
                                "description": "Max occupancy if labeled",
                            },
                            "has_net": {"type": "boolean", "description": "Whether court has a net"},
                            "confidence": {"type": "number", "description": "Confidence score 0-1"},
                        },
                        "required": [
                            "label",
                            "length_ft",
                            "width_ft",
                            "sqft",
                            "surface_type",
                            "max_occupancy",
                            "has_net",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                },
                "buffer_zones": {
                    "type": "array",
                    "description": "Buffer zones between courts",
                    "items": {
                        "type": "object",
                        "properties": {
                            "between_courts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Courts this buffer is between",
                            },
                            "width_ft": {"type": "number", "description": "Buffer width in feet"},
                            "length_ft": {"type": "number", "description": "Buffer length in feet"},
                            "sqft": {"type": "number", "description": "Buffer square footage"},
                            "confidence": {"type": "number", "description": "Confidence score 0-1"},
                        },
                        "required": ["between_courts", "width_ft", "length_ft", "sqft", "confidence"],
                        "additionalProperties": False,
                    },
                },
                "circulation_areas": {
                    "type": "array",
                    "description": "Circulation/walkway areas",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Area label"},
                            "sqft": {"type": "number", "description": "Area square footage"},
                            "surface_type": {
                                "type": "string",
                                "enum": SURFACE_TYPES,
                                "description": "Surface material type",
                            },
                            "is_hex_textured": {
                                "type": "boolean",
                                "description": "Whether surface has hex texture pattern",
                            },
                            "confidence": {"type": "number", "description": "Confidence score 0-1"},
                        },
                        "required": ["label", "sqft", "surface_type", "is_hex_textured", "confidence"],
                        "additionalProperties": False,
                    },
                },
                "auxiliary_areas": {
                    "type": "array",
                    "description": "Auxiliary areas (pro shop, office, etc.)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Area label"},
                            "sqft": {"type": "number", "description": "Area square footage"},
                            "surface_type": {
                                "type": "string",
                                "enum": SURFACE_TYPES,
                                "description": "Surface material type",
                            },
                            "cleanable_by_robot": {
                                "type": "boolean",
                                "description": "Whether robots can clean this area",
                            },
                            "confidence": {"type": "number", "description": "Confidence score 0-1"},
                        },
                        "required": ["label", "sqft", "surface_type", "cleanable_by_robot", "confidence"],
                        "additionalProperties": False,
                    },
                },
                "excluded_areas": {
                    "type": "array",
                    "description": "Areas excluded from robot cleaning",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Area label"},
                            "sqft": {"type": "number", "description": "Area square footage"},
                            "reason": {
                                "type": "string",
                                "enum": EXCLUSION_REASONS,
                                "description": "Reason for exclusion",
                            },
                            "confidence": {"type": "number", "description": "Confidence score 0-1"},
                        },
                        "required": ["label", "sqft", "reason", "confidence"],
                        "additionalProperties": False,
                    },
                },
                "obstructions": {
                    "type": "array",
                    "description": "Obstructions affecting robot navigation",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": OBSTRUCTION_TYPES,
                                "description": "Type of obstruction",
                            },
                            "location": {"type": "string", "description": "Location description"},
                            "handling": {
                                "type": "string",
                                "enum": OBSTRUCTION_HANDLING,
                                "description": "How robot handles this",
                            },
                        },
                        "required": ["type", "location", "handling"],
                        "additionalProperties": False,
                    },
                },
                "summary": {
                    "type": "object",
                    "description": "Summary of extracted features",
                    "properties": {
                        "total_court_sqft": {
                            "type": "number",
                            "description": "Total court square footage",
                        },
                        "total_circulation_sqft": {
                            "type": "number",
                            "description": "Total circulation/buffer square footage",
                        },
                        "total_auxiliary_sqft": {
                            "type": "number",
                            "description": "Total auxiliary area square footage",
                        },
                        "total_excluded_sqft": {
                            "type": "number",
                            "description": "Total excluded area square footage",
                        },
                        "total_cleanable_sqft": {
                            "type": "number",
                            "description": "Total cleanable square footage",
                        },
                        "court_count": {"type": "integer", "description": "Number of courts detected"},
                    },
                    "required": [
                        "total_court_sqft",
                        "total_circulation_sqft",
                        "total_auxiliary_sqft",
                        "total_excluded_sqft",
                        "total_cleanable_sqft",
                        "court_count",
                    ],
                    "additionalProperties": False,
                },
                "extraction_notes": {
                    "type": "string",
                    "description": "Notes about assumptions or unclear elements in the floor plan",
                },
            },
            "required": [
                "facility_dimensions",
                "courts",
                "buffer_zones",
                "circulation_areas",
                "auxiliary_areas",
                "excluded_areas",
                "obstructions",
                "summary",
                "extraction_notes",
            ],
            "additionalProperties": False,
        },
    },
}
