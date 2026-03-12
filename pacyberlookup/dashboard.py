"""Interactive CLI dashboard — `pacyberlookup status`.

Shows recent incidents, source health, last poll times, entity counts,
and overall feed health at a glance.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Entity, Incident, RawMention

logger = logging.getLogger(__name__)


def get_status(session: Session, hours: int = 24) -> dict:
    """Gather all status data for the dashboard.

    Args:
        session: Database session.
        hours: Lookback period in hours.

    Returns:
        Dict with all dashboard data.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)

    # Entity counts
    total_entities = session.query(Entity).count()
    watched_entities = session.query(Entity).filter(Entity.watched.is_(True)).count()
    client_entities = session.query(Entity).filter(Entity.is_client_or_prospect.is_(True)).count()

    # Recent incidents
    recent_incidents = (
        session.query(Incident)
        .filter(Incident.detected_at >= cutoff)
        .order_by(Incident.confidence_score.desc())
        .all()
    )
    high = [i for i in recent_incidents if i.confidence_band == "High"]
    medium = [i for i in recent_incidents if i.confidence_band == "Medium"]
    low = [i for i in recent_incidents if i.confidence_band == "Low"]
    noise = [i for i in recent_incidents if i.confidence_band == "Noise"]

    # Client/prospect hits
    client_hits = [i for i in recent_incidents if i.mapped_client_or_prospect]

    # Source health: count raw mentions by source_type in last period
    source_health = (
        session.query(RawMention.source_type, func.count(RawMention.id))
        .filter(RawMention.created_at >= cutoff)
        .group_by(RawMention.source_type)
        .all()
    )

    # Last raw mention time (most recent poll indicator)
    last_mention = (
        session.query(func.max(RawMention.created_at)).scalar()
    )

    # Last incident time
    last_incident = (
        session.query(func.max(Incident.detected_at)).scalar()
    )

    # All-time totals
    total_incidents = session.query(Incident).count()
    total_mentions = session.query(RawMention).count()

    # By county (recent)
    county_counts = {}
    for i in recent_incidents:
        if i.county:
            county_counts[i.county] = county_counts.get(i.county, 0) + 1

    # By type (recent)
    type_counts = {}
    for i in recent_incidents:
        if i.incident_type:
            type_counts[i.incident_type] = type_counts.get(i.incident_type, 0) + 1

    return {
        "now": now,
        "period_hours": hours,
        "total_entities": total_entities,
        "watched_entities": watched_entities,
        "client_entities": client_entities,
        "recent_total": len(recent_incidents),
        "recent_high": len(high),
        "recent_medium": len(medium),
        "recent_low": len(low),
        "recent_noise": len(noise),
        "client_hits": len(client_hits),
        "source_health": dict(source_health),
        "last_mention_at": last_mention,
        "last_incident_at": last_incident,
        "total_incidents_alltime": total_incidents,
        "total_mentions_alltime": total_mentions,
        "county_counts": county_counts,
        "type_counts": type_counts,
        "top_incidents": (high + medium)[:10],
        "client_incidents": client_hits,
    }


def render_dashboard(status: dict) -> str:
    """Render the dashboard as a formatted CLI string."""
    now = status["now"].strftime("%Y-%m-%d %H:%M UTC")
    hours = status["period_hours"]

    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  PA CYBER WATCH — FEED STATUS DASHBOARD")
    lines.append("=" * 60)
    lines.append(f"  Generated: {now}")
    lines.append(f"  Period: Last {hours} hours")
    lines.append("")

    # Entity summary
    lines.append("  ENTITIES")
    lines.append(f"    Total:             {status['total_entities']}")
    lines.append(f"    Watched:           {status['watched_entities']}")
    lines.append(f"    Client/Prospect:   {status['client_entities']}")
    lines.append("")

    # Incident summary
    lines.append("  INCIDENTS (last {hours}h)")
    lines.append(f"    High Confidence:   {status['recent_high']}")
    lines.append(f"    Medium Confidence: {status['recent_medium']}")
    lines.append(f"    Low Confidence:    {status['recent_low']}")
    lines.append(f"    Noise:             {status['recent_noise']}")
    lines.append(f"    Total:             {status['recent_total']}")
    if status["client_hits"]:
        lines.append(f"    CLIENT/PROSPECT:   {status['client_hits']}  <<<")
    lines.append("")

    # All-time
    lines.append("  ALL TIME")
    lines.append(f"    Total incidents:   {status['total_incidents_alltime']}")
    lines.append(f"    Total mentions:    {status['total_mentions_alltime']}")
    lines.append("")

    # Source health
    lines.append("  SOURCE HEALTH (last {hours}h)")
    if status["source_health"]:
        for source_type, count in sorted(status["source_health"].items(),
                                          key=lambda x: -x[1]):
            indicator = "OK" if count > 0 else "NO DATA"
            lines.append(f"    {source_type:<20s} {count:>5d} mentions  [{indicator}]")
    else:
        lines.append("    No source data in period")
    lines.append("")

    # Last activity
    last_m = status["last_mention_at"]
    last_i = status["last_incident_at"]
    now_naive = status["now"].replace(tzinfo=None)
    lines.append("  LAST ACTIVITY")
    if last_m:
        lm = last_m.replace(tzinfo=None) if last_m.tzinfo else last_m
        ago = now_naive - lm
        lines.append(f"    Last mention:      {last_m.strftime('%Y-%m-%d %H:%M')} ({_format_ago(ago)})")
    else:
        lines.append("    Last mention:      Never")
    if last_i:
        li = last_i.replace(tzinfo=None) if last_i.tzinfo else last_i
        ago = now_naive - li
        lines.append(f"    Last incident:     {last_i.strftime('%Y-%m-%d %H:%M')} ({_format_ago(ago)})")
    else:
        lines.append("    Last incident:     Never")
    lines.append("")

    # Top incidents
    if status["top_incidents"]:
        lines.append("  TOP INCIDENTS")
        for inc in status["top_incidents"][:8]:
            band = inc.confidence_band or "?"
            score = inc.confidence_score or 0
            entity = (inc.entity_name or "Unknown")[:30]
            itype = (inc.incident_type or "unknown")[:15]
            src = (inc.source or "")[:20]
            lines.append(f"    [{band:>6s} {score:>3.0f}] {entity:<30s} {itype:<15s} {src}")
        lines.append("")

    # Client/prospect alerts
    if status["client_incidents"]:
        lines.append("  CLIENT/PROSPECT ALERTS")
        for inc in status["client_incidents"]:
            lines.append(f"    >>> {inc.entity_name} — {inc.incident_type} [{inc.confidence_band}]")
        lines.append("")

    # County breakdown
    if status["county_counts"]:
        lines.append("  BY COUNTY")
        for county, count in sorted(status["county_counts"].items(), key=lambda x: -x[1])[:8]:
            bar = "#" * min(count, 30)
            lines.append(f"    {county:<20s} {count:>3d} {bar}")
        lines.append("")

    # Incident type breakdown
    if status["type_counts"]:
        lines.append("  BY INCIDENT TYPE")
        for itype, count in sorted(status["type_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"    {itype:<20s} {count:>3d}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def _format_ago(delta: timedelta) -> str:
    """Format a timedelta as a human-readable 'ago' string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h {minutes % 60}m ago"
    days = hours // 24
    return f"{days}d {hours % 24}h ago"


def print_dashboard(session: Session, hours: int = 24):
    """Get status and print the dashboard."""
    status = get_status(session, hours)
    print(render_dashboard(status))
