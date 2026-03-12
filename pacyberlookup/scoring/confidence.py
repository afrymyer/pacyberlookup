"""Confidence scoring model for PA cyber incident mentions.

Scores each mention 0-100 based on:
- Source credibility
- Entity match quality
- Incident language strength
- Cross-source validation
"""

import re

from rapidfuzz import fuzz

from ..sources.base import SourceMention
from ..utils.text import normalize_text


class ConfidenceScorer:
    """Score source mentions by confidence."""

    def __init__(self, config: dict):
        scoring_cfg = config.get("scoring", {})
        self.source_weights = scoring_cfg.get("source_credibility", {
            "government_advisory": 35,
            "local_regional_news": 25,
            "national_news": 20,
            "social_mention": 5,
        })
        self.entity_weights = scoring_cfg.get("entity_match", {
            "exact_name": 25,
            "alias": 15,
            "geography_only": 5,
        })
        self.language_weights = scoring_cfg.get("incident_language", {
            "confirmed": 25,
            "probable": 15,
            "unconfirmed": 5,
        })
        self.cross_source_weights = scoring_cfg.get("cross_source", {
            "two_sources": 15,
            "three_plus_sources": 25,
        })
        thresholds = scoring_cfg.get("thresholds", {})
        self.high_threshold = thresholds.get("high", 75)
        self.medium_threshold = thresholds.get("medium", 50)
        self.low_threshold = thresholds.get("low", 25)

        self.confirmed_terms = config.get("incident_keywords", {}).get(
            "confirmed_terms", ["confirmed breach", "ransomware attack", "data breach"]
        )
        self.probable_terms = config.get("incident_keywords", {}).get(
            "probable_terms", ["security incident", "network disruption"]
        )
        self.unconfirmed_terms = config.get("incident_keywords", {}).get(
            "unconfirmed_terms", ["rumored", "possible", "unconfirmed"]
        )

    def score_source_credibility(self, mention: SourceMention) -> int:
        """Score based on source type."""
        return self.source_weights.get(mention.source_credibility, 0)

    def score_entity_match(
        self,
        text: str,
        entity_name: str,
        aliases: list[str],
    ) -> tuple[int, str | None]:
        """Score based on how well the text matches a known entity.

        Returns:
            Tuple of (score, matched_alias_or_name).
        """
        text_norm = normalize_text(text)
        entity_norm = normalize_text(entity_name)

        # Exact match
        if entity_norm in text_norm:
            return self.entity_weights.get("exact_name", 25), entity_name

        # Alias match
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if alias_norm in text_norm:
                return self.entity_weights.get("alias", 15), alias

        # Fuzzy match on entity name (high threshold)
        ratio = fuzz.partial_ratio(entity_norm, text_norm)
        if ratio >= 85:
            return self.entity_weights.get("alias", 15), entity_name

        return 0, None

    def score_incident_language(self, text: str) -> int:
        """Score based on strength of incident language in text."""
        text_lower = text.lower() if text else ""

        for term in self.confirmed_terms:
            if term.lower() in text_lower:
                return self.language_weights.get("confirmed", 25)

        for term in self.probable_terms:
            if term.lower() in text_lower:
                return self.language_weights.get("probable", 15)

        for term in self.unconfirmed_terms:
            if term.lower() in text_lower:
                return self.language_weights.get("unconfirmed", 5)

        return 0

    def score_cross_source(self, source_count: int) -> int:
        """Score based on number of independent sources."""
        if source_count >= 3:
            return self.cross_source_weights.get("three_plus_sources", 25)
        if source_count >= 2:
            return self.cross_source_weights.get("two_sources", 15)
        return 0

    def compute_total_score(
        self,
        mention: SourceMention,
        entity_name: str = "",
        aliases: list[str] | None = None,
        source_count: int = 1,
    ) -> dict:
        """Compute the full confidence score for a mention.

        Returns:
            Dict with score breakdown and total.
        """
        aliases = aliases or []
        text = f"{mention.headline} {mention.raw_text}"

        source_score = self.score_source_credibility(mention)
        entity_score, matched = self.score_entity_match(text, entity_name, aliases)
        language_score = self.score_incident_language(text)
        cross_score = self.score_cross_source(source_count)

        total = min(100, source_score + entity_score + language_score + cross_score)

        return {
            "total": total,
            "source_credibility": source_score,
            "entity_match": entity_score,
            "incident_language": language_score,
            "cross_source": cross_score,
            "matched_alias": matched,
            "confidence_band": self.get_band(total),
        }

    def get_band(self, score: float) -> str:
        """Return the confidence band for a score."""
        if score >= self.high_threshold:
            return "High"
        if score >= self.medium_threshold:
            return "Medium"
        if score >= self.low_threshold:
            return "Low"
        return "Noise"

    def get_category(self, score: float, source_type: str = "") -> str:
        """Return the output category for a score and source type."""
        if source_type == "cisa":
            return "Official Advisory / Risk Context"
        if score >= self.high_threshold:
            return "Confirmed Incident"
        if score >= self.medium_threshold:
            return "Suspected Incident"
        if source_type == "social":
            return "Social Chatter / Needs Verification"
        return "Social Chatter / Needs Verification"
