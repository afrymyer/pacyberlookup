"""Entity seeding from CSV files."""

import csv
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Entity, EntityAlias

logger = logging.getLogger(__name__)

DEFAULT_SEED_FILE = Path(__file__).parent.parent / "seed_data" / "pa_entities.csv"


def seed_entities(session: Session, csv_path: str | None = None):
    """Load entities and aliases from a CSV file into the database.

    CSV format:
        EntityName,EntityType,County,Region,Website,PriorityTier,IsClientOrProspect,Watched,Aliases

    Aliases column should be pipe-delimited (e.g., "Alias One|Alias Two|Alias Three").
    """
    path = Path(csv_path) if csv_path else DEFAULT_SEED_FILE

    if not path.exists():
        logger.error("Seed file not found: %s", path)
        return

    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("EntityName", "").strip()
            if not name:
                continue

            # Check if entity already exists
            existing = session.query(Entity).filter(Entity.entity_name == name).first()
            if existing:
                logger.debug("Entity already exists: %s", name)
                continue

            entity = Entity(
                entity_name=name,
                entity_type=row.get("EntityType", "").strip(),
                county=row.get("County", "").strip(),
                region=row.get("Region", "").strip(),
                website=row.get("Website", "").strip(),
                priority_tier=int(row.get("PriorityTier", "2") or "2"),
                is_client_or_prospect=row.get("IsClientOrProspect", "").strip().lower() in ("yes", "true", "1"),
                watched=row.get("Watched", "yes").strip().lower() in ("yes", "true", "1"),
            )
            session.add(entity)
            session.flush()

            # Add aliases
            aliases_str = row.get("Aliases", "")
            if aliases_str:
                for alias in aliases_str.split("|"):
                    alias = alias.strip()
                    if alias and alias.lower() != name.lower():
                        session.add(EntityAlias(entity_id=entity.id, alias=alias))

            count += 1

    session.commit()
    logger.info("Seeded %d entities from %s", count, path)
