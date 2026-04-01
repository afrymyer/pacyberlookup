"""Tests for configuration loading."""

import tempfile
from pathlib import Path

from pacyberlookup.utils.config import load_config


class TestLoadConfig:
    def test_loads_valid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("polling:\n  news_interval_minutes: 30\n")
            f.flush()
            config = load_config(f.name)
        assert config["polling"]["news_interval_minutes"] == 30

    def test_missing_file_returns_empty(self):
        config = load_config("/tmp/nonexistent-config-xyz.yaml")
        assert config == {}

    def test_malformed_yaml_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{{invalid yaml: [unterminated")
            f.flush()
            config = load_config(f.name)
        assert config == {}

    def test_empty_yaml_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            config = load_config(f.name)
        assert config == {}

    def test_yaml_with_only_scalar_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("just a string")
            f.flush()
            config = load_config(f.name)
        assert config == {}
