"""Tests for new source modules: HIBP, OTX, Ransomware.live, Shadowserver."""

from pacyberlookup.sources.hibp import HIBPSource
from pacyberlookup.sources.otx import OTXSource
from pacyberlookup.sources.ransomware_live import RansomwareLiveSource
from pacyberlookup.sources.shadowserver import ShadowserverSource
from pacyberlookup.utils.config import load_config


def _make_config():
    return load_config()


# ── HIBP ──

def test_hibp_source_properties():
    source = HIBPSource(_make_config())
    assert source.source_name == "Have I Been Pwned"
    assert source.source_type == "hibp"


def test_hibp_no_api_key_skips_domain_monitoring(monkeypatch):
    """Without API key, domain monitoring should return empty."""
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    source = HIBPSource(_make_config())
    result = source._check_monitored_domains()
    assert result == []


# ── OTX ──

def test_otx_source_properties():
    source = OTXSource(_make_config())
    assert source.source_name == "AlienVault OTX"
    assert source.source_type == "threat_intel"


def test_otx_no_api_key_still_works(monkeypatch):
    """OTX should work without API key (public search)."""
    monkeypatch.delenv("OTX_API_KEY", raising=False)
    source = OTXSource(_make_config())
    assert source._get_api_key() == ""


# ── Ransomware.live ──

def test_ransomware_live_source_properties():
    source = RansomwareLiveSource(_make_config())
    assert source.source_name == "Ransomware.live"
    assert source.source_type == "ransomware_leak"


# ── Shadowserver ──

def test_shadowserver_source_properties():
    source = ShadowserverSource(_make_config())
    assert source.source_name == "Shadowserver"
    assert source.source_type == "threat_intel"


def test_shadowserver_no_api_key_skips_reports(monkeypatch):
    """Without API credentials, should skip detailed reports."""
    monkeypatch.delenv("SHADOWSERVER_API_KEY", raising=False)
    monkeypatch.delenv("SHADOWSERVER_API_SECRET", raising=False)
    source = ShadowserverSource(_make_config())
    result = source._fetch_reports("", "", [])
    assert result == []
