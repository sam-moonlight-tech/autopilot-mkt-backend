#!/usr/bin/env python
"""Script to extract structured sales knowledge from call transcripts.

Usage:
    python scripts/extract_call_knowledge.py

This script processes PDF transcripts from Discovery and Greenlight calls,
extracts structured knowledge using OpenAI, and outputs JSON files for
the sales knowledge service.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF
from openai import OpenAI

from src.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
DISCOVERY_DIR = PROJECT_ROOT / "Discovery Calls"
GREENLIGHT_DIR = PROJECT_ROOT / "Greenlight Call"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

# Extraction prompts
DISCOVERY_EXTRACTION_PROMPT = """Analyze this sales call transcript and extract structured knowledge.
This is a DISCOVERY call where prospects are learning about cleaning robots for their pickleball/sports facilities.

Extract the following categories. For each item, preserve the customer's exact language when relevant.

Return a JSON object with these fields:

{
  "facility_profile": {
    "name": "facility name if mentioned",
    "type": "facility type (indoor/outdoor pickleball, multi-sport, etc)",
    "court_count": number or null,
    "court_surface": "surface type if mentioned",
    "square_footage": number or null,
    "staff_size": number or null,
    "notable_details": ["any other relevant details"]
  },
  "pain_points": [
    {
      "category": "time|labor|quality|cost|health|court_preservation",
      "customer_quote": "exact or near-exact customer language",
      "context": "brief context about the situation"
    }
  ],
  "questions_asked": [
    {
      "question": "question the prospect asked",
      "topic": "cleaning|pricing|durability|compatibility|operations|other",
      "context": "why they asked this"
    }
  ],
  "objections": [
    {
      "objection": "the concern or objection raised",
      "category": "price|timing|trust|technical|budget",
      "context": "situation around the objection"
    }
  ],
  "buying_signals": [
    {
      "signal": "what indicated interest",
      "strength": "weak|moderate|strong"
    }
  ],
  "timeline_context": {
    "urgency": "immediate|soon|future|exploring",
    "details": "any timeline details mentioned"
  }
}

Only include items that are actually present in the transcript. Leave arrays empty if no items found.
Be selective - only extract high-quality, actionable insights.

TRANSCRIPT:
"""

GREENLIGHT_EXTRACTION_PROMPT = """Analyze this sales call transcript and extract structured knowledge.
This is a GREENLIGHT call focused on closing the sale, pricing discussions, and final objection handling.

Extract the following categories. Preserve exact language when relevant.

Return a JSON object with these fields:

{
  "facility_profile": {
    "name": "facility name if mentioned",
    "type": "facility type",
    "deal_size": "number of robots or monthly value if mentioned"
  },
  "pricing_discussions": [
    {
      "topic": "what was discussed",
      "customer_position": "their stance or concern",
      "resolution": "how it was addressed"
    }
  ],
  "objection_responses": [
    {
      "objection": "the objection raised",
      "category": "price|timing|budget|authority|trust",
      "response_given": "how it was addressed",
      "outcome": "accepted|deferred|unresolved"
    }
  ],
  "roi_discussions": [
    {
      "current_cost": "what they're spending now",
      "proposed_cost": "robot solution cost",
      "savings_argument": "ROI justification used",
      "customer_reaction": "how they responded"
    }
  ],
  "closing_triggers": [
    {
      "trigger": "what moved them toward decision",
      "category": "timeline|value|trust|urgency|comparison"
    }
  ],
  "negotiation_outcomes": {
    "final_price": "agreed price if mentioned",
    "terms": "special terms negotiated",
    "next_steps": "what was agreed"
  }
}

Only include items actually present. Be selective for high-quality insights.

TRANSCRIPT:
"""


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text content from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        str: Extracted text content.
    """
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return ""


def extract_knowledge_with_llm(
    client: OpenAI,
    transcript: str,
    prompt_template: str,
    source_file: str,
) -> dict[str, Any] | None:
    """Use OpenAI to extract structured knowledge from transcript.

    Args:
        client: OpenAI client.
        transcript: The transcript text.
        prompt_template: The extraction prompt.
        source_file: Source filename for reference.

    Returns:
        dict: Extracted knowledge or None if failed.
    """
    # Truncate very long transcripts to fit context
    max_chars = 100000  # ~25k tokens for context
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n...[truncated]..."

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting structured sales insights from call transcripts. Return only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt_template + transcript
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        if content:
            result = json.loads(content)
            result["_source"] = source_file
            return result
        return None

    except Exception as e:
        logger.error(f"LLM extraction failed for {source_file}: {e}")
        return None


def merge_discovery_knowledge(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple discovery call extractions into consolidated knowledge.

    Args:
        extractions: List of extraction results.

    Returns:
        dict: Consolidated knowledge base.
    """
    knowledge = {
        "personas": [],
        "pain_points": [],
        "questions_asked": [],
        "objections": [],
        "buying_signals": [],
    }

    for ext in extractions:
        source = ext.get("_source", "unknown")

        # Add facility profile as persona
        if profile := ext.get("facility_profile"):
            if profile.get("name") or profile.get("type"):
                knowledge["personas"].append({
                    **profile,
                    "source": source
                })

        # Merge pain points
        for pp in ext.get("pain_points", []):
            if pp.get("customer_quote"):
                knowledge["pain_points"].append({**pp, "source": source})

        # Merge questions
        for q in ext.get("questions_asked", []):
            if q.get("question"):
                knowledge["questions_asked"].append({**q, "source": source})

        # Merge objections
        for obj in ext.get("objections", []):
            if obj.get("objection"):
                knowledge["objections"].append({**obj, "source": source})

        # Merge buying signals
        for sig in ext.get("buying_signals", []):
            if sig.get("signal"):
                knowledge["buying_signals"].append({**sig, "source": source})

    return knowledge


def merge_greenlight_knowledge(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple greenlight call extractions into consolidated knowledge.

    Args:
        extractions: List of extraction results.

    Returns:
        dict: Consolidated knowledge base.
    """
    knowledge = {
        "objection_responses": [],
        "roi_examples": [],
        "closing_triggers": [],
        "pricing_insights": [],
    }

    for ext in extractions:
        source = ext.get("_source", "unknown")

        # Merge objection responses
        for obj in ext.get("objection_responses", []):
            if obj.get("objection") and obj.get("response_given"):
                knowledge["objection_responses"].append({**obj, "source": source})

        # Merge ROI discussions as examples
        for roi in ext.get("roi_discussions", []):
            if roi.get("savings_argument"):
                knowledge["roi_examples"].append({**roi, "source": source})

        # Merge closing triggers
        for trigger in ext.get("closing_triggers", []):
            if trigger.get("trigger"):
                knowledge["closing_triggers"].append({**trigger, "source": source})

        # Merge pricing discussions
        for pricing in ext.get("pricing_discussions", []):
            if pricing.get("topic"):
                knowledge["pricing_insights"].append({**pricing, "source": source})

    return knowledge


async def main() -> None:
    """Extract knowledge from all call transcripts."""
    logger.info("Starting knowledge extraction...")

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Ensure output directory exists
    KNOWLEDGE_DIR.mkdir(exist_ok=True)

    # Process Discovery calls
    logger.info("Processing Discovery calls...")
    discovery_extractions = []

    discovery_files = list(DISCOVERY_DIR.glob("*.pdf"))
    logger.info(f"Found {len(discovery_files)} Discovery call PDFs")

    for pdf_path in discovery_files:
        logger.info(f"Processing: {pdf_path.name}")
        transcript = extract_text_from_pdf(pdf_path)

        if not transcript:
            logger.warning(f"No text extracted from {pdf_path.name}")
            continue

        extraction = extract_knowledge_with_llm(
            client,
            transcript,
            DISCOVERY_EXTRACTION_PROMPT,
            pdf_path.name,
        )

        if extraction:
            discovery_extractions.append(extraction)
            logger.info(f"  Extracted knowledge from {pdf_path.name}")

    # Process Greenlight calls
    logger.info("Processing Greenlight calls...")
    greenlight_extractions = []

    greenlight_files = list(GREENLIGHT_DIR.glob("*.pdf"))
    logger.info(f"Found {len(greenlight_files)} Greenlight call PDFs")

    for pdf_path in greenlight_files:
        logger.info(f"Processing: {pdf_path.name}")
        transcript = extract_text_from_pdf(pdf_path)

        if not transcript:
            logger.warning(f"No text extracted from {pdf_path.name}")
            continue

        extraction = extract_knowledge_with_llm(
            client,
            transcript,
            GREENLIGHT_EXTRACTION_PROMPT,
            pdf_path.name,
        )

        if extraction:
            greenlight_extractions.append(extraction)
            logger.info(f"  Extracted knowledge from {pdf_path.name}")

    # Merge and save knowledge
    logger.info("Merging discovery knowledge...")
    discovery_knowledge = merge_discovery_knowledge(discovery_extractions)

    logger.info("Merging greenlight knowledge...")
    greenlight_knowledge = merge_greenlight_knowledge(greenlight_extractions)

    # Save individual JSON files
    output_files = {
        "personas.json": discovery_knowledge["personas"],
        "pain_points.json": discovery_knowledge["pain_points"],
        "questions_asked.json": discovery_knowledge["questions_asked"],
        "objections_discovery.json": discovery_knowledge["objections"],
        "buying_signals.json": discovery_knowledge["buying_signals"],
        "objection_responses.json": greenlight_knowledge["objection_responses"],
        "roi_examples.json": greenlight_knowledge["roi_examples"],
        "closing_triggers.json": greenlight_knowledge["closing_triggers"],
        "pricing_insights.json": greenlight_knowledge["pricing_insights"],
    }

    for filename, data in output_files.items():
        output_path = KNOWLEDGE_DIR / filename
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {filename} with {len(data)} items")

    # Save raw extractions for reference
    with open(KNOWLEDGE_DIR / "_raw_discovery_extractions.json", "w") as f:
        json.dump(discovery_extractions, f, indent=2)

    with open(KNOWLEDGE_DIR / "_raw_greenlight_extractions.json", "w") as f:
        json.dump(greenlight_extractions, f, indent=2)

    logger.info("Knowledge extraction complete!")
    logger.info(f"Output saved to: {KNOWLEDGE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
