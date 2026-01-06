"""Sales knowledge service for phase-specific context injection."""

import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Knowledge directory
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "knowledge"


class SalesKnowledgeService:
    """Service for loading and retrieving sales knowledge by conversation phase."""

    def __init__(self) -> None:
        """Initialize sales knowledge service."""
        self._knowledge: dict[str, list[dict[str, Any]]] = {}
        self._loaded = False

    def _load_knowledge(self) -> None:
        """Load all knowledge files from disk."""
        if self._loaded:
            return

        knowledge_files = [
            "personas.json",
            "pain_points.json",
            "questions_asked.json",
            "objections_discovery.json",
            "objection_responses.json",
            "roi_examples.json",
            "closing_triggers.json",
            "pricing_insights.json",
            "buying_signals.json",
        ]

        for filename in knowledge_files:
            filepath = KNOWLEDGE_DIR / filename
            key = filename.replace(".json", "")
            try:
                if filepath.exists():
                    with open(filepath) as f:
                        self._knowledge[key] = json.load(f)
                    logger.debug(f"Loaded {len(self._knowledge[key])} items from {filename}")
                else:
                    self._knowledge[key] = []
                    logger.warning(f"Knowledge file not found: {filepath}")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")
                self._knowledge[key] = []

        self._loaded = True
        logger.info(f"Sales knowledge loaded from {KNOWLEDGE_DIR}")

    def _format_pain_points(self, items: list[dict[str, Any]], limit: int = 3) -> str:
        """Format pain points for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["Common customer pain points you can probe:"]
        for item in selected:
            quote = item.get("customer_quote", "")
            category = item.get("category", "")
            if quote:
                lines.append(f"- [{category}] \"{quote}\"")
        return "\n".join(lines)

    def _format_questions(self, items: list[dict[str, Any]], limit: int = 4) -> str:
        """Format common questions for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["Questions prospects commonly ask:"]
        for item in selected:
            question = item.get("question", "")
            topic = item.get("topic", "")
            if question:
                lines.append(f"- [{topic}] {question}")
        return "\n".join(lines)

    def _format_objections(self, items: list[dict[str, Any]], limit: int = 3) -> str:
        """Format objections for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["Common objections to be prepared for:"]
        for item in selected:
            objection = item.get("objection", "")
            category = item.get("category", "")
            if objection:
                lines.append(f"- [{category}] {objection}")
        return "\n".join(lines)

    def _format_objection_responses(self, items: list[dict[str, Any]], limit: int = 3) -> str:
        """Format objection-response pairs for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["Objection handling examples:"]
        for item in selected:
            objection = item.get("objection", "")
            response = item.get("response_given", "")
            if objection and response:
                lines.append(f"- Objection: \"{objection}\"")
                lines.append(f"  Response: {response}")
        return "\n".join(lines)

    def _format_roi_examples(self, items: list[dict[str, Any]], limit: int = 2) -> str:
        """Format ROI examples for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["ROI calculation examples from similar customers:"]
        for item in selected:
            current = item.get("current_cost", "")
            proposed = item.get("proposed_cost", "")
            argument = item.get("savings_argument", "")
            if current and proposed:
                lines.append(f"- Current: {current}")
                lines.append(f"  Proposed: {proposed}")
                if argument:
                    lines.append(f"  Value: {argument}")
        return "\n".join(lines)

    def _format_closing_triggers(self, items: list[dict[str, Any]], limit: int = 3) -> str:
        """Format closing triggers for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["What typically triggers purchase decisions:"]
        for item in selected:
            trigger = item.get("trigger", "")
            category = item.get("category", "")
            if trigger:
                lines.append(f"- [{category}] {trigger}")
        return "\n".join(lines)

    def _format_buying_signals(self, items: list[dict[str, Any]], limit: int = 3) -> str:
        """Format buying signals for context injection."""
        if not items:
            return ""

        selected = random.sample(items, min(limit, len(items)))
        lines = ["Buying signals to watch for:"]
        for item in selected:
            signal = item.get("signal", "")
            strength = item.get("strength", "")
            if signal:
                lines.append(f"- [{strength}] {signal}")
        return "\n".join(lines)

    def get_discovery_context(self, max_tokens: int = 800) -> str:
        """Get sales knowledge context for DISCOVERY phase.

        Returns context to help the agent:
        - Probe common pain points
        - Anticipate frequently asked questions
        - Recognize buying signals

        Args:
            max_tokens: Approximate token budget (not exact).

        Returns:
            str: Formatted knowledge context for system prompt.
        """
        self._load_knowledge()

        sections = []

        # Pain points to probe
        pain_points = self._format_pain_points(
            self._knowledge.get("pain_points", []), limit=4
        )
        if pain_points:
            sections.append(pain_points)

        # Common questions to prepare for
        questions = self._format_questions(
            self._knowledge.get("questions_asked", []), limit=4
        )
        if questions:
            sections.append(questions)

        # Buying signals to watch for
        signals = self._format_buying_signals(
            self._knowledge.get("buying_signals", []), limit=3
        )
        if signals:
            sections.append(signals)

        # Discovery-phase objections
        objections = self._format_objections(
            self._knowledge.get("objections_discovery", []), limit=3
        )
        if objections:
            sections.append(objections)

        if not sections:
            return ""

        header = "=== SALES KNOWLEDGE (from real customer conversations) ==="
        return header + "\n\n" + "\n\n".join(sections)

    def get_roi_context(self, max_tokens: int = 800) -> str:
        """Get sales knowledge context for ROI phase.

        Returns context to help the agent:
        - Provide ROI calculation examples
        - Reference real cost comparisons
        - Support value justification

        Args:
            max_tokens: Approximate token budget.

        Returns:
            str: Formatted knowledge context for system prompt.
        """
        self._load_knowledge()

        sections = []

        # ROI examples from real customers
        roi = self._format_roi_examples(
            self._knowledge.get("roi_examples", []), limit=3
        )
        if roi:
            sections.append(roi)

        # Pain points (for value reinforcement)
        pain_points = self._format_pain_points(
            self._knowledge.get("pain_points", []), limit=3
        )
        if pain_points:
            sections.append(pain_points)

        if not sections:
            return ""

        header = "=== SALES KNOWLEDGE (from real customer conversations) ==="
        return header + "\n\n" + "\n\n".join(sections)

    def get_greenlight_context(self, max_tokens: int = 1000) -> str:
        """Get sales knowledge context for GREENLIGHT phase.

        Returns context to help the agent:
        - Handle objections with proven responses
        - Leverage closing triggers
        - Navigate pricing discussions

        Args:
            max_tokens: Approximate token budget.

        Returns:
            str: Formatted knowledge context for system prompt.
        """
        self._load_knowledge()

        sections = []

        # Objection-response pairs
        objection_responses = self._format_objection_responses(
            self._knowledge.get("objection_responses", []), limit=4
        )
        if objection_responses:
            sections.append(objection_responses)

        # Closing triggers
        triggers = self._format_closing_triggers(
            self._knowledge.get("closing_triggers", []), limit=4
        )
        if triggers:
            sections.append(triggers)

        # ROI reinforcement
        roi = self._format_roi_examples(
            self._knowledge.get("roi_examples", []), limit=2
        )
        if roi:
            sections.append(roi)

        if not sections:
            return ""

        header = "=== SALES KNOWLEDGE (from real customer conversations) ==="
        return header + "\n\n" + "\n\n".join(sections)


# Singleton instance
_sales_knowledge_service: SalesKnowledgeService | None = None


def get_sales_knowledge_service() -> SalesKnowledgeService:
    """Get sales knowledge service singleton.

    Returns:
        SalesKnowledgeService: Service instance.
    """
    global _sales_knowledge_service
    if _sales_knowledge_service is None:
        _sales_knowledge_service = SalesKnowledgeService()
    return _sales_knowledge_service
