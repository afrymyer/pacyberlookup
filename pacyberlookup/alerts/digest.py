"""Scheduled daily/weekly digest reports via email and Teams.

Generates morning summaries with overnight activity, trend counts,
watchlist hits, and source health.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Entity, Incident, IncidentSource

logger = logging.getLogger(__name__)


def build_digest_data(session: Session, hours: int = 24) -> dict:
    """Gather digest data for the last N hours.

    Returns:
        Dict with summary stats and incident lists.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Recent incidents
    recent = (
        session.query(Incident)
        .filter(Incident.detected_at >= cutoff)
        .order_by(Incident.confidence_score.desc())
        .all()
    )

    # Group by band
    high = [i for i in recent if i.confidence_band == "High"]
    medium = [i for i in recent if i.confidence_band == "Medium"]
    low = [i for i in recent if i.confidence_band == "Low"]

    # Client/prospect hits
    client_hits = [i for i in recent if i.mapped_client_or_prospect]

    # By county
    county_counts = {}
    for i in recent:
        if i.county:
            county_counts[i.county] = county_counts.get(i.county, 0) + 1

    # By incident type
    type_counts = {}
    for i in recent:
        if i.incident_type:
            type_counts[i.incident_type] = type_counts.get(i.incident_type, 0) + 1

    # By source type
    source_counts = {}
    for i in recent:
        if i.source_type:
            source_counts[i.source_type] = source_counts.get(i.source_type, 0) + 1

    # Total entity count
    entity_count = session.query(Entity).filter(Entity.watched.is_(True)).count()

    # Trending: entities with most incidents in period
    entity_incident_counts = {}
    for i in recent:
        if i.entity_name:
            entity_incident_counts[i.entity_name] = entity_incident_counts.get(
                i.entity_name, 0
            ) + 1
    trending = sorted(entity_incident_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "period_hours": hours,
        "generated_at": datetime.now(timezone.utc),
        "total_incidents": len(recent),
        "high_count": len(high),
        "medium_count": len(medium),
        "low_count": len(low),
        "client_prospect_hits": len(client_hits),
        "high_incidents": high,
        "medium_incidents": medium,
        "low_incidents": low,
        "client_incidents": client_hits,
        "county_counts": county_counts,
        "type_counts": type_counts,
        "source_counts": source_counts,
        "entity_count": entity_count,
        "trending_entities": trending,
    }


def format_digest_teams_card(data: dict) -> dict:
    """Format digest data as a Teams Adaptive Card."""
    now = data["generated_at"].strftime("%Y-%m-%d %H:%M UTC")
    hours = data["period_hours"]

    facts = [
        {"title": "Period", "value": f"Last {hours} hours"},
        {"title": "Total Incidents", "value": str(data["total_incidents"])},
        {"title": "High Confidence", "value": str(data["high_count"])},
        {"title": "Medium Confidence", "value": str(data["medium_count"])},
        {"title": "Low Confidence", "value": str(data["low_count"])},
        {"title": "Client/Prospect Hits", "value": str(data["client_prospect_hits"])},
        {"title": "Watched Entities", "value": str(data["entity_count"])},
    ]

    body = [
        {
            "type": "TextBlock",
            "text": f"PA Cyber Watch Daily Digest",
            "weight": "Bolder",
            "size": "Medium",
            "style": "heading",
        },
        {
            "type": "TextBlock",
            "text": f"Generated: {now}",
            "isSubtle": True,
            "size": "Small",
        },
        {"type": "FactSet", "facts": facts},
    ]

    # Top incidents
    if data["high_incidents"] or data["medium_incidents"]:
        body.append({
            "type": "TextBlock",
            "text": "Top Incidents",
            "weight": "Bolder",
            "spacing": "Medium",
        })
        top = (data["high_incidents"] + data["medium_incidents"])[:5]
        for inc in top:
            body.append({
                "type": "TextBlock",
                "text": (
                    f"**[{inc.confidence_band}]** {inc.entity_name or 'Unknown'} — "
                    f"{inc.incident_type or 'Unknown'} ({inc.source})"
                ),
                "wrap": True,
                "size": "Small",
            })

    # Trending entities
    if data["trending_entities"]:
        body.append({
            "type": "TextBlock",
            "text": "Trending Entities",
            "weight": "Bolder",
            "spacing": "Medium",
        })
        for name, count in data["trending_entities"]:
            body.append({
                "type": "TextBlock",
                "text": f"{name}: {count} mentions",
                "size": "Small",
            })

    # County breakdown
    if data["county_counts"]:
        top_counties = sorted(data["county_counts"].items(), key=lambda x: -x[1])[:5]
        body.append({
            "type": "TextBlock",
            "text": "By County: " + ", ".join(f"{c} ({n})" for c, n in top_counties),
            "size": "Small",
            "isSubtle": True,
            "spacing": "Medium",
        })

    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
            },
        }],
    }
    return card


def format_digest_html(data: dict) -> str:
    """Format digest data as HTML for email."""
    from .email import format_incident_html

    now = data["generated_at"].strftime("%Y-%m-%d %H:%M UTC")
    hours = data["period_hours"]

    parts = [
        f"<h1>PA Cyber Watch Daily Digest</h1>",
        f"<p>Period: Last {hours} hours | Generated: {now}</p>",
        "<h2>Summary</h2>",
        "<table style='font-size:14px; border-collapse:collapse;'>",
        f"<tr><td style='padding:4px 12px;'><strong>Total Incidents:</strong></td><td>{data['total_incidents']}</td></tr>",
        f"<tr><td style='padding:4px 12px;'><strong>High Confidence:</strong></td><td style='color:#d32f2f;'>{data['high_count']}</td></tr>",
        f"<tr><td style='padding:4px 12px;'><strong>Medium Confidence:</strong></td><td style='color:#f57c00;'>{data['medium_count']}</td></tr>",
        f"<tr><td style='padding:4px 12px;'><strong>Low Confidence:</strong></td><td style='color:#1976d2;'>{data['low_count']}</td></tr>",
        f"<tr><td style='padding:4px 12px;'><strong>Client/Prospect Hits:</strong></td><td style='color:#d32f2f; font-weight:bold;'>{data['client_prospect_hits']}</td></tr>",
        f"<tr><td style='padding:4px 12px;'><strong>Watched Entities:</strong></td><td>{data['entity_count']}</td></tr>",
        "</table>",
    ]

    # Client/prospect alerts (top priority)
    if data["client_incidents"]:
        parts.append(f"<h2>Client/Prospect Alerts ({len(data['client_incidents'])})</h2>")
        for inc in data["client_incidents"]:
            parts.append(format_incident_html(_incident_to_dict(inc)))

    # High confidence
    if data["high_incidents"]:
        parts.append(f"<h2>High Confidence ({data['high_count']})</h2>")
        for inc in data["high_incidents"]:
            parts.append(format_incident_html(_incident_to_dict(inc)))

    # Medium confidence
    if data["medium_incidents"]:
        parts.append(f"<h2>Medium Confidence ({data['medium_count']})</h2>")
        for inc in data["medium_incidents"][:10]:
            parts.append(format_incident_html(_incident_to_dict(inc)))

    # Trending
    if data["trending_entities"]:
        parts.append("<h2>Trending Entities</h2><ul>")
        for name, count in data["trending_entities"]:
            parts.append(f"<li><strong>{name}</strong>: {count} mentions</li>")
        parts.append("</ul>")

    # County breakdown
    if data["county_counts"]:
        parts.append("<h2>By County</h2><ul>")
        for county, count in sorted(data["county_counts"].items(), key=lambda x: -x[1]):
            parts.append(f"<li>{county}: {count}</li>")
        parts.append("</ul>")

    return "\n".join(parts)


def _incident_to_dict(inc: Incident) -> dict:
    """Convert an Incident ORM object to a dict for formatting."""
    return {
        "entity_name": inc.entity_name,
        "county": inc.county,
        "entity_type": inc.entity_type,
        "incident_type": inc.incident_type,
        "confidence_band": inc.confidence_band,
        "confidence_score": inc.confidence_score,
        "ai_summary": inc.ai_summary,
        "summary": inc.summary,
        "headline": inc.headline,
        "url": inc.url,
        "source": inc.source,
    }


def send_digest(session: Session, hours: int = 24) -> bool:
    """Generate and send the digest via email and Teams.

    Args:
        session: Database session.
        hours: How many hours to look back.

    Returns:
        True if at least one delivery method succeeded.
    """
    import requests as req

    data = build_digest_data(session, hours)
    success = False

    # Teams digest
    webhook_url = os.getenv("TEAMS_DIGEST_WEBHOOK_URL", "") or os.getenv("TEAMS_WEBHOOK_URL", "")
    if webhook_url:
        try:
            card = format_digest_teams_card(data)
            resp = req.post(webhook_url, json=card, timeout=15)
            resp.raise_for_status()
            logger.info("Digest posted to Teams")
            success = True
        except Exception:
            logger.exception("Failed to post digest to Teams")

    # Email digest
    if os.getenv("EMAIL_ENABLED", "false").lower() == "true":
        try:
            from .email import send_digest_email

            incidents = []
            for inc in (data["high_incidents"] + data["medium_incidents"] + data["low_incidents"]):
                incidents.append(_incident_to_dict(inc))

            now = data["generated_at"].strftime("%Y-%m-%d")
            subject = f"PA Cyber Watch Daily Digest - {now}"
            if send_digest_email(incidents, subject):
                success = True
        except Exception:
            logger.exception("Failed to send digest email")

    if not success:
        logger.warning("No digest delivery methods succeeded (check Teams/email config)")

    return success
