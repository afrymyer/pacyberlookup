"""Power BI data export layer.

Exports incident data to formats consumable by Power BI:
- CSV/Excel files for Power BI Desktop import
- Structured JSON for Power BI streaming datasets
- Direct SQL views via the SQLAlchemy database

Recommended Power BI tables:
- dim_entities_pa: Entity reference dimension
- dim_keywords_incident: Keyword/incident type dimension
- fact_source_mentions: Raw mention facts
- fact_incidents_scored: Scored incidents
- fact_incidents_deduped: Deduplicated final incidents
"""

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Entity, EntityAlias, Incident, IncidentSource, RawMention

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("exports")


def ensure_export_dir():
    """Create exports directory if needed."""
    EXPORT_DIR.mkdir(exist_ok=True)


def export_entities_csv(session: Session, path: str | None = None) -> str:
    """Export dim_entities_pa to CSV for Power BI."""
    ensure_export_dir()
    path = path or str(EXPORT_DIR / "dim_entities_pa.csv")

    entities = session.query(Entity).all()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "EntityID", "EntityName", "EntityType", "County", "Region",
            "Website", "PriorityTier", "IsClientOrProspect", "Watched",
            "Aliases",
        ])
        for e in entities:
            aliases = "; ".join(a.alias for a in e.aliases)
            writer.writerow([
                e.id, e.entity_name, e.entity_type, e.county, e.region,
                e.website, e.priority_tier, e.is_client_or_prospect,
                e.watched, aliases,
            ])

    logger.info("Exported %d entities to %s", len(entities), path)
    return path


def export_incidents_csv(session: Session, path: str | None = None) -> str:
    """Export fact_incidents_scored to CSV for Power BI."""
    ensure_export_dir()
    path = path or str(EXPORT_DIR / "fact_incidents_scored.csv")

    incidents = session.query(Incident).order_by(Incident.detected_at.desc()).all()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "IncidentID", "DetectedAt", "PublishedAt", "EntityName",
            "MatchedAlias", "EntityType", "County", "Headline", "Source",
            "SourceType", "URL", "IncidentType", "Summary",
            "ConfidenceScore", "ConfidenceBand", "Category",
            "VerificationStatus", "DuplicateGroupID",
            "RequiresAction", "MappedClientOrProspect", "AISummary",
        ])
        for i in incidents:
            writer.writerow([
                i.id, i.detected_at, i.published_at, i.entity_name,
                i.matched_alias, i.entity_type, i.county, i.headline,
                i.source, i.source_type, i.url, i.incident_type,
                i.summary, i.confidence_score, i.confidence_band,
                i.category, i.verification_status, i.duplicate_group_id,
                i.requires_action, i.mapped_client_or_prospect, i.ai_summary,
            ])

    logger.info("Exported %d incidents to %s", len(incidents), path)
    return path


def export_incidents_json(session: Session, path: str | None = None) -> str:
    """Export incidents as JSON for Power BI streaming dataset or API."""
    ensure_export_dir()
    path = path or str(EXPORT_DIR / "fact_incidents_scored.json")

    incidents = session.query(Incident).order_by(Incident.detected_at.desc()).all()
    records = []
    for i in incidents:
        records.append({
            "IncidentID": i.id,
            "DetectedAt": i.detected_at.isoformat() if i.detected_at else None,
            "PublishedAt": i.published_at.isoformat() if i.published_at else None,
            "EntityName": i.entity_name,
            "MatchedAlias": i.matched_alias,
            "EntityType": i.entity_type,
            "County": i.county,
            "Headline": i.headline,
            "Source": i.source,
            "SourceType": i.source_type,
            "URL": i.url,
            "IncidentType": i.incident_type,
            "Summary": i.summary,
            "ConfidenceScore": i.confidence_score,
            "ConfidenceBand": i.confidence_band,
            "Category": i.category,
            "VerificationStatus": i.verification_status,
            "DuplicateGroupID": i.duplicate_group_id,
            "RequiresAction": i.requires_action,
            "MappedClientOrProspect": i.mapped_client_or_prospect,
            "AISummary": i.ai_summary,
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    logger.info("Exported %d incidents to %s", len(records), path)
    return path


def export_all(session: Session) -> dict[str, str]:
    """Export all Power BI datasets."""
    return {
        "entities": export_entities_csv(session),
        "incidents_csv": export_incidents_csv(session),
        "incidents_json": export_incidents_json(session),
    }
