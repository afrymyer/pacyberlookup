"""AI summarization layer for scored incidents.

Generates structured summaries once an item passes a minimum confidence score.
Supports OpenAI-compatible APIs or falls back to template-based summaries.
"""

import os
import logging

logger = logging.getLogger(__name__)


def build_template_summary(incident: dict) -> str:
    """Build a structured summary using a template (no AI needed)."""
    entity = incident.get("entity_name", "Unknown")
    entity_type = incident.get("entity_type", "Unknown")
    incident_type = incident.get("incident_type", "Unknown")
    confidence_band = incident.get("confidence_band", "Unknown")
    headline = incident.get("headline", "")
    source = incident.get("source", "Unknown")
    source_count = incident.get("source_count", 1)
    county = incident.get("county", "Unknown")

    sources_str = source
    if source_count > 1:
        source_list = incident.get("source_mentions", [])
        source_names = list({m.get("source", "") for m in source_list if m.get("source")})
        sources_str = ", ".join(source_names[:5])

    status_map = {
        "High": "High confidence - likely confirmed",
        "Medium": "Medium confidence - credible but needs review",
        "Low": "Low confidence - possible lead",
        "Noise": "Noise - hold for analyst review",
    }
    status = status_map.get(confidence_band, "Unknown")

    next_steps = {
        "High": "Monitor for official statement. Consider client/prospect outreach.",
        "Medium": "Watch for second-source validation or official confirmation.",
        "Low": "Hold for additional reporting. Check back in 24-48 hours.",
        "Noise": "Suppress unless corroborated by credible source.",
    }
    next_step = next_steps.get(confidence_band, "Review manually.")

    return (
        f"Organization: {entity}\n"
        f"Type: {entity_type}\n"
        f"County: {county}\n"
        f"Incident: {incident_type}\n"
        f"Status: {status}\n"
        f"What happened: {headline}\n"
        f"Source(s): {sources_str}\n"
        f"Next step: {next_step}"
    )


def build_ai_summary(incident: dict) -> str | None:
    """Generate an AI-powered summary using an OpenAI-compatible API.

    Returns None if AI summarization is disabled or fails.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or os.getenv("AI_SUMMARIZATION_ENABLED", "false").lower() != "true":
        return None

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        entity = incident.get("entity_name", "Unknown")
        entity_type = incident.get("entity_type", "Unknown")
        headline = incident.get("headline", "")
        raw_text = incident.get("raw_text", "")
        source = incident.get("source", "")

        prompt = (
            "You are a cybersecurity analyst summarizing a potential cyber incident "
            "for an IT managed services company monitoring Pennsylvania organizations.\n\n"
            f"Entity: {entity}\n"
            f"Type: {entity_type}\n"
            f"Headline: {headline}\n"
            f"Source: {source}\n"
            f"Text: {raw_text[:1000]}\n\n"
            "Provide a concise structured summary with:\n"
            "- What happened (1-2 sentences)\n"
            "- Likely incident type\n"
            "- Recommended next step for the monitoring team\n"
            "Keep it under 100 words."
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("AI summarization failed")
        return None


def summarize_incident(incident: dict) -> str:
    """Generate the best available summary for an incident."""
    ai_summary = build_ai_summary(incident)
    if ai_summary:
        return ai_summary
    return build_template_summary(incident)
