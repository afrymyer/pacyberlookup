"""Source health monitoring.

Tracks which sources returned data, errored, or returned zero results.
Alerts if a source has been failing for multiple cycles.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import Session

from .models import Base

logger = logging.getLogger(__name__)


class SourceHealthRecord(Base):
    """Per-source health record for each poll cycle."""

    __tablename__ = "source_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    source_type = Column(String(50))
    cycle_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), nullable=False)  # ok, error, empty
    mention_count = Column(Integer, default=0)
    duration_ms = Column(Float, default=0.0)
    error_message = Column(String(1000))


class SourceHealthTracker:
    """Track and query source health across cycles."""

    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        source_name: str,
        source_type: str,
        status: str,
        mention_count: int = 0,
        duration_ms: float = 0.0,
        error_message: str = "",
    ):
        """Record a health entry for a source after a poll."""
        record = SourceHealthRecord(
            source_name=source_name,
            source_type=source_type,
            status=status,
            mention_count=mention_count,
            duration_ms=duration_ms,
            error_message=error_message[:1000] if error_message else "",
        )
        self.session.add(record)
        self.session.commit()

    def get_recent(self, hours: int = 24) -> list[dict]:
        """Get health records for the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        records = (
            self.session.query(SourceHealthRecord)
            .filter(SourceHealthRecord.cycle_time >= cutoff)
            .order_by(SourceHealthRecord.cycle_time.desc())
            .all()
        )
        return [
            {
                "source_name": r.source_name,
                "source_type": r.source_type,
                "cycle_time": r.cycle_time,
                "status": r.status,
                "mention_count": r.mention_count,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
            }
            for r in records
        ]

    def get_summary(self, hours: int = 24) -> dict[str, dict]:
        """Get a per-source health summary for the last N hours.

        Returns:
            Dict keyed by source_name with stats about each source.
        """
        records = self.get_recent(hours)
        summary: dict[str, dict] = {}

        for r in records:
            name = r["source_name"]
            if name not in summary:
                summary[name] = {
                    "source_type": r["source_type"],
                    "total_cycles": 0,
                    "ok_cycles": 0,
                    "error_cycles": 0,
                    "empty_cycles": 0,
                    "total_mentions": 0,
                    "avg_duration_ms": 0.0,
                    "last_ok": None,
                    "last_error": None,
                    "last_error_message": "",
                    "consecutive_failures": 0,
                }

            s = summary[name]
            s["total_cycles"] += 1

            if r["status"] == "ok":
                s["ok_cycles"] += 1
                s["total_mentions"] += r["mention_count"]
                if s["last_ok"] is None or r["cycle_time"] > s["last_ok"]:
                    s["last_ok"] = r["cycle_time"]
            elif r["status"] == "error":
                s["error_cycles"] += 1
                if s["last_error"] is None or r["cycle_time"] > s["last_error"]:
                    s["last_error"] = r["cycle_time"]
                    s["last_error_message"] = r["error_message"]
            elif r["status"] == "empty":
                s["empty_cycles"] += 1

        # Calculate consecutive failures and avg duration
        for name, s in summary.items():
            if s["total_cycles"] > 0:
                durations = [
                    r["duration_ms"] for r in records
                    if r["source_name"] == name and r["duration_ms"] > 0
                ]
                if durations:
                    s["avg_duration_ms"] = sum(durations) / len(durations)

            # Count consecutive failures from most recent
            source_records = sorted(
                [r for r in records if r["source_name"] == name],
                key=lambda r: r["cycle_time"],
                reverse=True,
            )
            consec = 0
            for r in source_records:
                if r["status"] in ("error", "empty"):
                    consec += 1
                else:
                    break
            s["consecutive_failures"] = consec

        return summary

    def get_failing_sources(self, min_consecutive: int = 3, hours: int = 24) -> list[dict]:
        """Get sources that have been failing for multiple consecutive cycles.

        Args:
            min_consecutive: Minimum consecutive failures to report.
            hours: Lookback period.

        Returns:
            List of failing source dicts.
        """
        summary = self.get_summary(hours)
        failing = []
        for name, s in summary.items():
            if s["consecutive_failures"] >= min_consecutive:
                failing.append({
                    "source_name": name,
                    "consecutive_failures": s["consecutive_failures"],
                    "last_ok": s["last_ok"],
                    "last_error_message": s["last_error_message"],
                })
        return failing

    def render_health_table(self, hours: int = 24) -> str:
        """Render a CLI-friendly health summary table."""
        summary = self.get_summary(hours)
        if not summary:
            return "  No source health data available."

        lines = []
        lines.append(f"  {'Source':<25s} {'Status':<8s} {'OK':>3s} {'Err':>3s} {'Empty':>5s} {'Mentions':>8s} {'Consec Fail':>11s}")
        lines.append("  " + "-" * 75)

        for name in sorted(summary.keys()):
            s = summary[name]
            # Determine status indicator
            if s["consecutive_failures"] >= 3:
                status = "FAILING"
            elif s["consecutive_failures"] >= 1:
                status = "WARN"
            elif s["ok_cycles"] > 0:
                status = "OK"
            else:
                status = "UNKNOWN"

            lines.append(
                f"  {name:<25s} {status:<8s} {s['ok_cycles']:>3d} {s['error_cycles']:>3d} "
                f"{s['empty_cycles']:>5d} {s['total_mentions']:>8d} "
                f"{s['consecutive_failures']:>11d}"
            )

        return "\n".join(lines)
