"""Configuration loader for PA Cyber Incident Detection Feed."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_config(config_path: str | None = None) -> dict:
    """Load settings from YAML config file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path) as f:
        return yaml.safe_load(f)


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with fallback."""
    return os.getenv(key, default)


def get_database_url() -> str:
    """Get database URL from environment or default."""
    return get_env("DATABASE_URL", "sqlite:///data/pacyberlookup.db")
