"""Email alert and digest delivery."""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def format_incident_html(incident: dict) -> str:
    """Format a single incident as an HTML block for email."""
    entity = incident.get("entity_name", "Unknown")
    county = incident.get("county", "Unknown")
    entity_type = incident.get("entity_type", "Unknown")
    incident_type = incident.get("incident_type", "Unknown")
    confidence_band = incident.get("confidence_band", "Unknown")
    confidence_score = incident.get("confidence_score", 0)
    summary = incident.get("ai_summary") or incident.get("summary", "")
    headline = incident.get("headline", "")
    url = incident.get("url", "")
    source = incident.get("source", "")

    color_map = {"High": "#d32f2f", "Medium": "#f57c00", "Low": "#1976d2", "Noise": "#757575"}
    color = color_map.get(confidence_band, "#757575")

    link_html = f'<a href="{url}">View Source</a>' if url else ""

    return f"""
    <div style="border-left: 4px solid {color}; padding: 12px; margin-bottom: 16px; background: #fafafa;">
        <h3 style="margin: 0 0 8px 0;">{entity}</h3>
        <table style="font-size: 14px;">
            <tr><td><strong>County:</strong></td><td>{county}</td></tr>
            <tr><td><strong>Type:</strong></td><td>{entity_type}</td></tr>
            <tr><td><strong>Incident:</strong></td><td>{incident_type}</td></tr>
            <tr><td><strong>Confidence:</strong></td><td>{confidence_band} ({confidence_score})</td></tr>
            <tr><td><strong>Source:</strong></td><td>{source}</td></tr>
        </table>
        <p style="margin: 8px 0;">{summary or headline}</p>
        {link_html}
    </div>
    """


def send_digest_email(incidents: list[dict], subject: str | None = None) -> bool:
    """Send a digest email with all scored incidents.

    Args:
        incidents: List of incident dicts to include.
        subject: Optional email subject line.

    Returns:
        True if email was sent successfully.
    """
    if os.getenv("EMAIL_ENABLED", "false").lower() != "true":
        logger.info("Email disabled; skipping digest")
        return False

    smtp_server = os.getenv("SMTP_SERVER", "")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        logger.error("Invalid SMTP_PORT value: %s", os.getenv("SMTP_PORT"))
        return False
    smtp_user = os.getenv("SMTP_USERNAME", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    email_from = os.getenv("EMAIL_FROM", smtp_user)
    email_to = os.getenv("EMAIL_TO", "")

    if not all([smtp_server, smtp_user, smtp_pass, email_to]):
        logger.warning("Email configuration incomplete; skipping digest")
        return False

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not subject:
        subject = f"PA Cyber Watch Digest - {now}"

    # Group by confidence band
    high = [i for i in incidents if i.get("confidence_band") == "High"]
    medium = [i for i in incidents if i.get("confidence_band") == "Medium"]
    low = [i for i in incidents if i.get("confidence_band") == "Low"]

    body_parts = [f"<h1>PA Cyber Watch Digest</h1><p>Generated: {now}</p>"]

    for label, group in [("High Confidence", high), ("Medium Confidence", medium), ("Low Confidence", low)]:
        if group:
            body_parts.append(f"<h2>{label} ({len(group)})</h2>")
            for inc in group:
                body_parts.append(format_incident_html(inc))

    if not (high or medium or low):
        body_parts.append("<p>No incidents above noise threshold in this cycle.</p>")

    html_body = "\n".join(body_parts)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, email_to.split(","), msg.as_string())
        logger.info("Digest email sent to %s", email_to)
        return True
    except Exception:
        logger.exception("Failed to send digest email")
        return False
