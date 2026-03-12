"""De-duplication logic for incident mentions.

Groups mentions into incidents using:
- Normalized entity name
- Incident type
- 7-day date window

Keeps: earliest mention, most authoritative source, most recent update.
"""

from datetime import datetime, timedelta, timezone

from ..utils.text import normalize_entity_name, extract_incident_type


def generate_dedup_key(entity_name: str, incident_type: str | None, date: datetime | None) -> str:
    """Generate a dedup key for grouping related mentions.

    Key format: {normalized_entity}|{incident_type}|{week_start}
    Week start is the Monday of the ISO week containing the date.
    """
    norm_entity = normalize_entity_name(entity_name) if entity_name else "unknown"
    inc_type = (incident_type or "unknown").lower().strip()

    if date:
        # Use 7-day window aligned to the date
        week_start = date - timedelta(days=date.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
    else:
        week_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"{norm_entity}|{inc_type}|{week_key}"


# Source authority ranking (lower = more authoritative)
SOURCE_AUTHORITY = {
    "government_advisory": 1,
    "local_regional_news": 2,
    "national_news": 3,
    "social_mention": 4,
    "unknown": 5,
}


def deduplicate_mentions(mentions: list[dict]) -> list[dict]:
    """Deduplicate a list of scored mention dicts.

    Each mention dict should have at minimum:
        entity_name, incident_type, published_at, source_credibility,
        confidence_score, and all other incident fields.

    Returns:
        List of deduplicated incident dicts, one per group.
        Each includes a 'source_mentions' list of all grouped mentions.
    """
    groups: dict[str, list[dict]] = {}

    for mention in mentions:
        entity_name = mention.get("entity_name", "")
        incident_type = mention.get("incident_type") or extract_incident_type(
            mention.get("raw_text", "")
        )
        published_at = mention.get("published_at")

        key = generate_dedup_key(entity_name, incident_type, published_at)
        groups.setdefault(key, []).append(mention)

    results = []
    for key, group in groups.items():
        # Sort by authority (most authoritative first), then by date (earliest first)
        group.sort(key=lambda m: (
            SOURCE_AUTHORITY.get(m.get("source_credibility", "unknown"), 5),
            m.get("published_at") or datetime.max.replace(tzinfo=timezone.utc),
        ))

        # The primary record is the most authoritative source
        primary = group[0].copy()

        # Use earliest published_at
        dates = [m["published_at"] for m in group if m.get("published_at")]
        if dates:
            primary["published_at"] = min(dates)

        # Use highest confidence score
        scores = [m.get("confidence_score", 0) for m in group]
        primary["confidence_score"] = max(scores)

        # Track all sources
        primary["source_mentions"] = group
        primary["source_count"] = len(group)
        primary["duplicate_group_id"] = key

        results.append(primary)

    return results
