"""Client/prospect watchlist overlay.

Routes incidents affecting clients/prospects with higher priority:
- Separate Teams channel via TEAMS_WATCHLIST_WEBHOOK_URL
- Auto-generated talking points for CAM/vCIO outreach
- Higher urgency flagging
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)


def generate_talking_points(incident: dict) -> str:
    """Generate CAM/vCIO outreach talking points for a client/prospect incident."""
    entity = incident.get("entity_name", "the organization")
    entity_type = incident.get("entity_type", "organization")
    incident_type = incident.get("incident_type", "cyber incident")
    confidence_band = incident.get("confidence_band", "Unknown")
    county = incident.get("county", "")
    source = incident.get("source", "")
    headline = incident.get("headline", "")

    points = [
        f"WATCHLIST ALERT: {entity} ({entity_type})",
        "",
        "Situation:",
        f"  Public reporting indicates a {incident_type} affecting {entity}.",
    ]

    if county:
        points.append(f"  Located in {county} County, Pennsylvania.")
    if source:
        points.append(f"  Source: {source}")
    if headline:
        points.append(f"  Headline: {headline}")

    points.append(f"  Confidence: {confidence_band}")
    points.append("")

    if confidence_band == "High":
        points.extend([
            "Recommended Actions:",
            "  1. Contact the account owner / vCISO immediately",
            "  2. Check if we have active services with this organization",
            "  3. Prepare a brief for leadership on potential impact",
            "  4. Draft an outreach message (support offer, not sales pitch)",
            "  5. Review our own exposure to shared infrastructure/vendors",
            "",
            "Outreach Talking Points:",
            f"  - We've been monitoring public reports about a {incident_type}",
            f"    affecting organizations in your area.",
            "  - We want to make sure you're aware and offer our support.",
            "  - If you need incident response assistance, we can mobilize quickly.",
            "  - We can also review your environment for similar vulnerabilities.",
        ])
    elif confidence_band == "Medium":
        points.extend([
            "Recommended Actions:",
            "  1. Monitor for confirmation from a second source",
            "  2. Flag for the account owner / vCISO",
            "  3. Prepare a soft outreach draft (hold until confirmed)",
            "  4. Check if the incident type affects our client's stack",
            "",
            "Outreach Talking Points (hold for confirmation):",
            f"  - We're tracking reports of a possible {incident_type}",
            f"    in your sector/region.",
            "  - No action needed yet, but we wanted you to be aware.",
            "  - We're monitoring the situation and will update you if needed.",
        ])
    else:
        points.extend([
            "Recommended Actions:",
            "  1. Log for awareness, no outreach needed yet",
            "  2. Watch for escalation in next 24-48 hours",
        ])

    return "\n".join(points)


def format_watchlist_teams_card(incident: dict, talking_points: str) -> dict:
    """Format a watchlist alert as a Teams Adaptive Card with talking points."""
    entity = incident.get("entity_name", "Unknown")
    county = incident.get("county", "Unknown")
    entity_type = incident.get("entity_type", "Unknown")
    incident_type = incident.get("incident_type", "Unknown")
    confidence_band = incident.get("confidence_band", "Unknown")
    confidence_score = incident.get("confidence_score", 0)
    summary = incident.get("ai_summary") or incident.get("summary", "")
    headline = incident.get("headline", "")
    url = incident.get("url", "")

    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "CLIENT/PROSPECT WATCHLIST ALERT",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Attention",
                        "style": "heading",
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Entity", "value": entity},
                            {"title": "County", "value": county},
                            {"title": "Type", "value": entity_type},
                            {"title": "Incident", "value": incident_type},
                            {"title": "Confidence", "value": f"{confidence_band} ({confidence_score})"},
                        ],
                    },
                    {
                        "type": "TextBlock",
                        "text": summary or headline,
                        "wrap": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": "Talking Points",
                        "weight": "Bolder",
                        "spacing": "Medium",
                    },
                    {
                        "type": "TextBlock",
                        "text": talking_points,
                        "wrap": True,
                        "fontType": "Monospace",
                        "size": "Small",
                    },
                ],
                "actions": [],
            },
        }],
    }

    if url:
        card["attachments"][0]["content"]["actions"].append({
            "type": "Action.OpenUrl",
            "title": "View Source",
            "url": url,
        })

    return card


def send_watchlist_alert(incident: dict) -> bool:
    """Send a watchlist alert with talking points to the dedicated Teams channel.

    Uses TEAMS_WATCHLIST_WEBHOOK_URL if set, falls back to TEAMS_WEBHOOK_URL.

    Returns:
        True if alert was sent successfully.
    """
    webhook_url = (
        os.getenv("TEAMS_WATCHLIST_WEBHOOK_URL", "")
        or os.getenv("TEAMS_WEBHOOK_URL", "")
    )
    if not webhook_url:
        logger.warning("No Teams webhook configured for watchlist alerts")
        return False

    talking_points = generate_talking_points(incident)
    card = format_watchlist_teams_card(incident, talking_points)

    try:
        resp = requests.post(webhook_url, json=card, timeout=15)
        resp.raise_for_status()
        logger.info(
            "Watchlist alert sent for client/prospect: %s",
            incident.get("entity_name", "Unknown"),
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send watchlist alert for: %s",
            incident.get("entity_name", "Unknown"),
        )
        return False
