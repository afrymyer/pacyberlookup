"""Tests for county-level geo enrichment."""

from pacyberlookup.geo import enrich_county, get_county_for_place


class TestEnrichCounty:
    def test_explicit_county_mention(self):
        assert enrich_county("Incident in Dauphin County reported today") == "Dauphin"

    def test_county_case_insensitive(self):
        assert enrich_county("dauphin county water system") == "Dauphin"

    def test_place_name_match(self):
        assert enrich_county("Harrisburg city network outage") == "Dauphin"

    def test_place_name_mechanicsburg(self):
        assert enrich_county("Mechanicsburg water system offline") == "Cumberland"

    def test_place_name_pittsburgh(self):
        assert enrich_county("Pittsburgh school district breach") == "Allegheny"

    def test_multi_word_place(self):
        assert enrich_county("Mount Lebanon systems compromised") == "Allegheny"

    def test_longer_match_priority(self):
        """'east stroudsburg' should match before 'stroudsburg'."""
        result = enrich_county("East Stroudsburg University breach")
        assert result == "Monroe"

    def test_no_match(self):
        assert enrich_county("Cyberattack hits company in California") is None

    def test_empty_text(self):
        assert enrich_county("") is None

    def test_none_text(self):
        assert enrich_county(None) is None

    def test_word_boundary(self):
        """'reading' should match Berks, not match substring 'threading'."""
        assert enrich_county("Reading hospital ransomware") == "Berks"

    def test_philadelphia(self):
        assert enrich_county("Philadelphia data breach reported") == "Philadelphia"

    def test_philly_alias(self):
        assert enrich_county("Philly water department hacked") == "Philadelphia"


class TestGetCountyForPlace:
    def test_known_place(self):
        assert get_county_for_place("harrisburg") == "Dauphin"

    def test_county_name(self):
        assert get_county_for_place("dauphin") == "Dauphin"

    def test_unknown_place(self):
        assert get_county_for_place("atlantis") is None
