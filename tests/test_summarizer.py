"""Tests for the summarization layer."""

from pacyberlookup.scoring.summarizer import build_template_summary


def test_template_summary_high():
    incident = {
        "entity_name": "Lower Swatara Township",
        "entity_type": "Municipality",
        "incident_type": "ransomware",
        "confidence_band": "High",
        "headline": "Township hit by ransomware",
        "source": "PennLive",
        "source_count": 2,
        "county": "Dauphin",
        "source_mentions": [
            {"source": "PennLive"},
            {"source": "KDKA"},
        ],
    }
    result = build_template_summary(incident)
    assert "Lower Swatara Township" in result
    assert "Municipality" in result
    assert "ransomware" in result
    assert "High confidence" in result
    assert "PennLive" in result
    assert "KDKA" in result


def test_template_summary_low():
    incident = {
        "entity_name": "Unknown",
        "entity_type": "Unknown",
        "incident_type": "unknown",
        "confidence_band": "Low",
        "headline": "Some post about possible issue",
        "source": "Reddit",
        "source_count": 1,
        "county": "Unknown",
    }
    result = build_template_summary(incident)
    assert "Low confidence" in result
    assert "Hold for additional reporting" in result
