"""Microsoft Teams webhook alert posting."""

import logging
import os

import requests

logger = logging.getLogger(__name__)


def format_teams_card(incident: dict) -> dict:
    """Format an incident as a Teams Adaptive Card payload.

    Creates a concise alert card for High/Medium confidence incidents.
    """
    entity = incident.get("entity_name", "Unknown")
    county = incident.get("county", "Unknown")
    entity_type = incident.get("entity_type", "Unknown")
    incident_type = incident.get("incident_type", "Unknown")
    confidence_band = incident.get("confidence_band", "Unknown")
    confidence_score = incident.get("confidence_score", 0)
    summary = incident.get("ai_summary") or incident.get("summary", "")
    headline = incident.get("headline", "")
    source = incident.get("source", "")
    url = incident.get("url", "")
    category = incident.get("category", "")

    color_map = {
        "High": "attention",
        "Medium": "warning",
        "Low": "accent",
        "Noise": "default",
    }
    color = color_map.get(confidence_band, "default")

    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "PA Cyber Watch Alert",
                            "weight": "Bolder",
                            "size": "Medium",
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
                                {"title": "Category", "value": category},
                                {"title": "Source", "value": source},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": summary or headline,
                            "wrap": True,
                        },
                    ],
                    "actions": [],
                },
            }
        ],
    }

    if url:
        card["attachments"][0]["content"]["actions"].append({
            "type": "Action.OpenUrl",
            "title": "View Source",
            "url": url,
        })

    return card


def send_teams_alert(incident: dict, webhook_url: str | None = None) -> bool:
    """Send an incident alert to Microsoft Teams via webhook.

    Args:
        incident: The incident dict to alert on.
        webhook_url: Teams webhook URL. Falls back to TEAMS_WEBHOOK_URL env var.

    Returns:
        True if the alert was sent successfully.
    """
    webhook_url = webhook_url or os.getenv("TEAMS_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("No Teams webhook URL configured; skipping alert")
        return False

    card = format_teams_card(incident)

    try:
        resp = requests.post(webhook_url, json=card, timeout=15)
        resp.raise_for_status()
        logger.info("Teams alert sent for: %s", incident.get("entity_name", "Unknown"))
        return True
    except Exception:
        logger.exception("Failed to send Teams alert for: %s",
                         incident.get("entity_name", "Unknown"))
        return False
