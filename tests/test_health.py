"""Tests for source health monitoring."""

from pacyberlookup.health import SourceHealthRecord, SourceHealthTracker
from pacyberlookup.models import init_db


def _setup_db():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()
    return session


class TestSourceHealthTracker:
    def test_record_and_get_recent(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("Google News", "news", "ok", mention_count=5, duration_ms=200)
        records = tracker.get_recent(hours=1)
        assert len(records) == 1
        assert records[0]["source_name"] == "Google News"
        assert records[0]["status"] == "ok"
        assert records[0]["mention_count"] == 5

    def test_record_error(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("CISA", "government", "error", error_message="Connection timeout")
        records = tracker.get_recent()
        assert records[0]["status"] == "error"
        assert records[0]["error_message"] == "Connection timeout"

    def test_get_summary(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("Google News", "news", "ok", mention_count=5, duration_ms=100)
        tracker.record("Google News", "news", "ok", mention_count=3, duration_ms=200)
        summary = tracker.get_summary()
        assert "Google News" in summary
        s = summary["Google News"]
        assert s["total_cycles"] == 2
        assert s["ok_cycles"] == 2
        assert s["total_mentions"] == 8
        assert s["consecutive_failures"] == 0

    def test_consecutive_failures(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("CISA", "government", "ok", mention_count=2)
        tracker.record("CISA", "government", "error", error_message="fail1")
        tracker.record("CISA", "government", "error", error_message="fail2")
        tracker.record("CISA", "government", "error", error_message="fail3")
        summary = tracker.get_summary()
        assert summary["CISA"]["consecutive_failures"] == 3

    def test_get_failing_sources(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        for i in range(4):
            tracker.record("BadSource", "test", "error", error_message=f"err{i}")
        tracker.record("GoodSource", "test", "ok", mention_count=1)
        failing = tracker.get_failing_sources(min_consecutive=3)
        assert len(failing) == 1
        assert failing[0]["source_name"] == "BadSource"
        assert failing[0]["consecutive_failures"] == 4

    def test_no_failing_when_ok(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("GoodSource", "test", "ok", mention_count=1)
        failing = tracker.get_failing_sources()
        assert len(failing) == 0

    def test_render_health_table_empty(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        result = tracker.render_health_table()
        assert "No source health data" in result

    def test_render_health_table_with_data(self):
        session = _setup_db()
        tracker = SourceHealthTracker(session)
        tracker.record("Google News", "news", "ok", mention_count=5)
        tracker.record("CISA", "government", "error", error_message="timeout")
        table = tracker.render_health_table()
        assert "Google News" in table
        assert "CISA" in table
