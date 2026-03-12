"""Tests for confidence scoring model."""

from pacyberlookup.scoring.confidence import ConfidenceScorer
from pacyberlookup.sources.base import SourceMention
from pacyberlookup.utils.config import load_config


def _make_config():
    """Load the default config for tests."""
    return load_config()


def _make_scorer():
    return ConfidenceScorer(_make_config())


def test_source_credibility_government():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="CISA Alert",
        source="CISA",
        source_type="cisa",
        source_credibility="government_advisory",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 35


def test_source_credibility_local_news():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="Local report",
        source="PennLive",
        source_type="news",
        source_credibility="local_regional_news",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 25


def test_source_credibility_social():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="Reddit post",
        source="Reddit",
        source_type="social",
        source_credibility="social_mention",
    )
    score = scorer.score_source_credibility(mention)
    assert score == 5


def test_entity_match_exact():
    scorer = _make_scorer()
    text = "Lower Swatara Township reports ransomware attack"
    score, matched = scorer.score_entity_match(text, "Lower Swatara Township", [])
    assert score == 25
    assert matched == "Lower Swatara Township"


def test_entity_match_alias():
    scorer = _make_scorer()
    text = "Lower Swatara Twp hit by breach"
    score, matched = scorer.score_entity_match(
        text, "Lower Swatara Township", ["Lower Swatara Twp", "Lower Swatara"]
    )
    assert score == 15
    assert matched == "Lower Swatara Twp"


def test_entity_match_none():
    scorer = _make_scorer()
    text = "California city reports outage"
    score, matched = scorer.score_entity_match(
        text, "Lower Swatara Township", ["Lower Swatara Twp"]
    )
    assert score == 0
    assert matched is None


def test_incident_language_confirmed():
    scorer = _make_scorer()
    score = scorer.score_incident_language("Township confirms data breach notification sent")
    assert score == 25


def test_incident_language_probable():
    scorer = _make_scorer()
    score = scorer.score_incident_language("Security incident under investigation")
    assert score == 15


def test_incident_language_unconfirmed():
    scorer = _make_scorer()
    score = scorer.score_incident_language("Rumored cyber event at borough")
    assert score == 5


def test_incident_language_none():
    scorer = _make_scorer()
    score = scorer.score_incident_language("Township approves new budget")
    assert score == 0


def test_cross_source_two():
    scorer = _make_scorer()
    assert scorer.score_cross_source(2) == 15


def test_cross_source_three_plus():
    scorer = _make_scorer()
    assert scorer.score_cross_source(3) == 25
    assert scorer.score_cross_source(5) == 25


def test_cross_source_one():
    scorer = _make_scorer()
    assert scorer.score_cross_source(1) == 0


def test_compute_total_high_confidence():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="Lower Swatara Township confirms ransomware attack",
        source="PennLive",
        source_type="news",
        raw_text="Lower Swatara Township confirms ransomware attack disrupting services",
        source_credibility="local_regional_news",
    )
    result = scorer.compute_total_score(
        mention,
        entity_name="Lower Swatara Township",
        aliases=["Lower Swatara Twp"],
        source_count=2,
    )
    # local_news(25) + exact_entity(25) + confirmed_language(25) + 2_sources(15) = 90
    assert result["total"] >= 75
    assert result["confidence_band"] == "High"


def test_compute_total_low_confidence():
    scorer = _make_scorer()
    mention = SourceMention(
        headline="Possible issue at some PA office",
        source="Reddit",
        source_type="social",
        raw_text="Heard rumors about possible issue",
        source_credibility="social_mention",
    )
    result = scorer.compute_total_score(
        mention,
        entity_name="Lower Swatara Township",
        aliases=[],
        source_count=1,
    )
    # social(5) + no entity match(0) + unconfirmed("possible")(5) = 10
    assert result["total"] < 50
    assert result["confidence_band"] in ("Low", "Noise")


def test_get_band():
    scorer = _make_scorer()
    assert scorer.get_band(80) == "High"
    assert scorer.get_band(60) == "Medium"
    assert scorer.get_band(30) == "Low"
    assert scorer.get_band(10) == "Noise"


def test_get_category():
    scorer = _make_scorer()
    assert scorer.get_category(80) == "Confirmed Incident"
    assert scorer.get_category(60) == "Suspected Incident"
    assert scorer.get_category(80, "cisa") == "Official Advisory / Risk Context"
