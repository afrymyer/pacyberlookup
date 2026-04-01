"""Base class for all source ingestion modules."""

import logging
import time
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

    # Minimum seconds between API calls. Override in subclass for rate-limited APIs.
    rate_limit_seconds: float = 0.0

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._last_request_time: float = 0.0

    def _rate_limit_wait(self):
        """Wait if needed to respect rate limits."""
        if self.rate_limit_seconds > 0:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit_seconds:
                wait = self.rate_limit_seconds - elapsed
                self.logger.debug("Rate limiting: waiting %.1fs", wait)
                time.sleep(wait)
            self._last_request_time = time.monotonic()

    @abstractmethod
    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch mentions from this source using the given search queries.

        Args:
            search_queries: List of search query strings to use.

        Returns:
            List of SourceMention objects found.
        """
        ...

    def fetch_with_retry(
        self, search_queries: list[str], max_retries: int = 2, backoff_base: float = 2.0
    ) -> list[SourceMention]:
        """Fetch with retry on transient network errors.

        Args:
            search_queries: Search queries to use.
            max_retries: Maximum retry attempts (default 2, so 3 total attempts).
            backoff_base: Base for exponential backoff in seconds.

        Returns:
            List of SourceMention objects.
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.fetch(search_queries)
            except (ConnectionError, TimeoutError, OSError) as e:
                last_error = e
                if attempt < max_retries:
                    wait = backoff_base ** attempt
                    self.logger.warning(
                        "%s: attempt %d failed (%s), retrying in %.1fs",
                        self.source_name, attempt + 1, e, wait,
                    )
                    time.sleep(wait)
                else:
                    self.logger.error(
                        "%s: all %d attempts failed", self.source_name, max_retries + 1,
                    )
                    raise
        raise last_error  # unreachable but satisfies type checker

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
