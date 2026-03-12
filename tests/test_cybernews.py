"""Tests for cybersecurity news RSS sources."""

from pacyberlookup.sources.cybernews import (
    BleepingComputerSource,
    DataBreachesNetSource,
    RecordedFutureSource,
    SecurityWeekSource,
    _clean_html,
    _parse_rss_feed,
)
from pacyberlookup.utils.config import load_config


def _make_config():
    return load_config()


def test_clean_html():
    assert _clean_html("<b>Test</b> content") == "Test content"
    assert _clean_html("") == ""
    assert _clean_html(None) == ""


def test_parse_rss_feed_invalid():
    """Invalid content should return empty list, not raise."""
    result = _parse_rss_feed(b"not valid xml")
    assert result == []


def test_bleeping_computer_source_properties():
    source = BleepingComputerSource(_make_config())
    assert source.source_name == "BleepingComputer"
    assert source.source_type == "news"


def test_security_week_source_properties():
    source = SecurityWeekSource(_make_config())
    assert source.source_name == "SecurityWeek"
    assert source.source_type == "news"


def test_databreaches_net_source_properties():
    source = DataBreachesNetSource(_make_config())
    assert source.source_name == "DataBreaches.net"
    assert source.source_type == "news"


def test_recorded_future_source_properties():
    source = RecordedFutureSource(_make_config())
    assert source.source_name == "Recorded Future"
    assert source.source_type == "news"


def test_bleeping_computer_keywords():
    source = BleepingComputerSource(_make_config())
    keywords = source._extract_keywords(["test query"])
    assert "breach" in keywords
    assert "ransomware" in keywords
    assert "pennsylvania" in keywords


def test_security_week_keywords():
    source = SecurityWeekSource(_make_config())
    keywords = source._extract_keywords(["test query"])
    assert "breach" in keywords
    assert "government" in keywords


def test_databreaches_net_keywords():
    source = DataBreachesNetSource(_make_config())
    keywords = source._extract_keywords(["test query"])
    assert "healthcare" in keywords
    assert "hospital" in keywords


def test_recorded_future_keywords():
    source = RecordedFutureSource(_make_config())
    keywords = source._extract_keywords(["test query"])
    assert "lockbit" in keywords
    assert "akira" in keywords
