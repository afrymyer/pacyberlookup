"""Tests for text normalization and matching utilities."""

from pacyberlookup.utils.text import (
    extract_incident_type,
    normalize_entity_name,
    normalize_text,
)


def test_normalize_text_basic():
    assert normalize_text("  Hello  World  ") == "hello world"


def test_normalize_text_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_normalize_entity_name_township_abbreviation():
    assert "township" in normalize_entity_name("Lower Swatara Twp")
    assert "township" in normalize_entity_name("Lower Swatara Twp.")


def test_normalize_entity_name_township_of():
    result = normalize_entity_name("Township of Lower Swatara")
    assert result == "lower swatara township"


def test_normalize_entity_name_borough_abbreviation():
    assert "borough" in normalize_entity_name("Middletown Boro")


def test_normalize_entity_name_school_district():
    assert "school district" in normalize_entity_name("Central Dauphin SD")


def test_extract_incident_type_ransomware():
    assert extract_incident_type("Township hit by ransomware attack") == "ransomware"


def test_extract_incident_type_breach():
    assert extract_incident_type("Data breach reported at county office") == "data breach"


def test_extract_incident_type_outage():
    assert extract_incident_type("Systems outage affects services") == "outage"


def test_extract_incident_type_cyberattack():
    assert extract_incident_type("Borough reports cyberattack on network") == "cyberattack"


def test_extract_incident_type_none():
    assert extract_incident_type("Weather forecast for Harrisburg") is None


def test_extract_incident_type_empty():
    assert extract_incident_type("") is None
    assert extract_incident_type(None) is None
