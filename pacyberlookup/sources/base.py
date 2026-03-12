"""Base class for all source ingestion modules."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SourceMention:
    """A single mention from any source, before scoring."""

    headline: str = ""
    source: str = ""
    source_type: str = ""  # news, gdelt, cisa, social
    url: str = ""
    raw_text: str = ""
    published_at: datetime | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_credibility: str = "unknown"  # government_advisory, local_regional_news, national_news, social_mention

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc)


class BaseSource(ABC):
    """Abstract base class for source ingestion."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch mentions from this source using the given search queries.

        Args:
            search_queries: List of search query strings to use.

        Returns:
            List of SourceMention objects found.
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of this source."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Source type identifier: news, gdelt, cisa, social."""
        ...
