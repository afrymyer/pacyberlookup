"""Tests for base source improvements: retry logic and rate limiting."""

import time
from unittest.mock import MagicMock, patch

from pacyberlookup.sources.base import BaseSource, SourceMention


class ConcreteSource(BaseSource):
    """Concrete test implementation of BaseSource."""

    rate_limit_seconds = 0.0  # No rate limiting by default in tests

    @property
    def source_name(self) -> str:
        return "TestSource"

    @property
    def source_type(self) -> str:
        return "test"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        return [SourceMention(headline="test", source="test", source_type="test")]


class FailingSource(BaseSource):
    """Source that fails with network errors."""

    def __init__(self, config, fail_count=2):
        super().__init__(config)
        self._attempts = 0
        self._fail_count = fail_count

    @property
    def source_name(self) -> str:
        return "FailingSource"

    @property
    def source_type(self) -> str:
        return "test"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            raise ConnectionError(f"Network error (attempt {self._attempts})")
        return [SourceMention(headline="recovered", source="test", source_type="test")]


class AlwaysFailingSource(BaseSource):
    """Source that always fails."""

    @property
    def source_name(self) -> str:
        return "AlwaysFailingSource"

    @property
    def source_type(self) -> str:
        return "test"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        raise ConnectionError("Permanent failure")


class TestFetchWithRetry:
    def test_success_no_retry(self):
        source = ConcreteSource({})
        result = source.fetch_with_retry(["test"])
        assert len(result) == 1
        assert result[0].headline == "test"

    @patch("pacyberlookup.sources.base.time.sleep")
    def test_retry_on_transient_failure(self, mock_sleep):
        source = FailingSource({}, fail_count=2)
        result = source.fetch_with_retry(["test"], max_retries=2, backoff_base=1.0)
        assert len(result) == 1
        assert result[0].headline == "recovered"
        assert source._attempts == 3
        assert mock_sleep.call_count == 2

    @patch("pacyberlookup.sources.base.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        source = AlwaysFailingSource({})
        try:
            source.fetch_with_retry(["test"], max_retries=2, backoff_base=1.0)
            assert False, "Should have raised ConnectionError"
        except ConnectionError:
            pass
        assert mock_sleep.call_count == 2

    @patch("pacyberlookup.sources.base.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        source = FailingSource({}, fail_count=3)
        source.fetch_with_retry(["test"], max_retries=3, backoff_base=2.0)
        # Backoff: 2^0=1, 2^1=2, 2^2=4
        waits = [call.args[0] for call in mock_sleep.call_args_list]
        assert waits == [1.0, 2.0, 4.0]


class TestRateLimiting:
    def test_rate_limit_wait_no_limit(self):
        source = ConcreteSource({})
        source.rate_limit_seconds = 0.0
        start = time.monotonic()
        source._rate_limit_wait()
        source._rate_limit_wait()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be instant

    def test_rate_limit_wait_with_limit(self):
        source = ConcreteSource({})
        source.rate_limit_seconds = 0.1
        source._last_request_time = time.monotonic()
        start = time.monotonic()
        source._rate_limit_wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # Should wait at least some time
