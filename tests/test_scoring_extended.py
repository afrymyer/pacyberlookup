"""Tests for extended scoring with new source types."""

from pacyberlookup.scoring.confidence import ConfidenceScorer
from pacyberlookup.sources.base import SourceMention
from pacyberlookup.utils.config import load_config


def _make_scorer():
    return ConfidenceScorer(load_config())


def test_source_credibility_ransomware_leak():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="LockBit posted victim",
        source="Ransomware.live",
        source_type="ransomware_leak",
        source_credibility="ransomware_leak",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 30


def test_source_credibility_breach_database():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="HIBP breach",
        source="Have I Been Pwned",
        source_type="hibp",
        source_credibility="breach_database",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 30


def test_source_credibility_threat_intel():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="OTX Pulse",
        source="AlienVault OTX",
        source_type="threat_intel",
        source_credibility="threat_intel",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 15


def test_category_ransomware_leak_medium():
    scorer = _make_scorer()
    # Ransomware leak with medium score -> Confirmed Incident
    assert scorer.get_category(55, "ransomware_leak") == "Confirmed Incident"


def test_category_ransomware_leak_low():
    scorer = _make_scorer()
    # Ransomware leak with low score -> Suspected Incident
    assert scorer.get_category(30, "ransomware_leak") == "Suspected Incident"


def test_category_threat_intel():
    scorer = _make_scorer()
    assert scorer.get_category(60, "threat_intel") == "Official Advisory / Risk Context"


def test_category_cisa_still_advisory():
    scorer = _make_scorer()
    assert scorer.get_category(80, "cisa") == "Official Advisory / Risk Context"


def test_ransomware_leak_high_confidence_scenario():
    """Ransomware.live + entity match + confirmed language = high confidence."""
    scorer = _make_scorer()
    mention = SourceMention(
        headline="LockBit posted Lower Swatara Township as ransomware victim",
        source="Ransomware.live (LockBit)",
        source_type="ransomware_leak",
        raw_text="LockBit ransomware group posted Lower Swatara Township data breach",
        source_credibility="ransomware_leak",
    )
    result = scorer.compute_total_score(
        mention,
        entity_name="Lower Swatara Township",
        aliases=["Lower Swatara Twp"],
        source_count=1,
    )
    # ransomware_leak(30) + exact_entity(25) + confirmed("data breach")(25) = 80
    assert result["total"] >= 75
    assert result["confidence_band"] == "High"
