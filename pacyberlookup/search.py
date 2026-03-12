"""Search query builder for PA cyber incident detection.

Generates structured search queries by combining:
- Pennsylvania geography / qualifiers
- Entity names / aliases
- Incident keywords
"""

from sqlalchemy.orm import Session

from .models import Entity, EntityAlias


def build_entity_queries(session: Session, config: dict) -> list[str]:
    """Build search queries for each watched entity.

    Generates queries like:
      "Lower Swatara Township" AND (breach OR ransomware OR cyberattack OR "security incident")
    """
    attack_terms = config.get("incident_keywords", {}).get("attack_terms", [])
    if not attack_terms:
        attack_terms = ["breach", "ransomware", "cyberattack", "security incident"]

    # Build the incident keyword OR group
    or_terms = " OR ".join(
        f'"{t}"' if " " in t else t for t in attack_terms[:8]  # limit to avoid overly long queries
    )
    incident_clause = f"({or_terms})"

    queries = []
    entities = session.query(Entity).filter(Entity.watched.is_(True)).all()

    for entity in entities:
        # Primary name query
        queries.append(f'"{entity.entity_name}" AND {incident_clause}')

        # Alias queries (limit to top 3 aliases to avoid excess)
        for alias in entity.aliases[:3]:
            if alias.alias.lower() != entity.entity_name.lower():
                queries.append(f'"{alias.alias}" AND {incident_clause}')

    return queries


def build_broad_queries(config: dict) -> list[str]:
    """Build broad discovery queries for PA geography + incident terms.

    Generates queries like:
      ("Pennsylvania" OR PA) AND ("township" OR borough) AND (breach OR ransomware)
    """
    pa_qualifiers = config.get("incident_keywords", {}).get(
        "pennsylvania_qualifiers", ["Pennsylvania", "PA"]
    )
    local_gov_terms = config.get("incident_keywords", {}).get("local_gov_terms", [])
    attack_terms = config.get("incident_keywords", {}).get("attack_terms", [])

    pa_clause = " OR ".join(f'"{q}"' if " " in q else q for q in pa_qualifiers)
    pa_clause = f"({pa_clause})"

    queries = []

    # PA + local gov type + incident keywords
    if local_gov_terms and attack_terms:
        gov_clause = " OR ".join(
            f'"{t}"' if " " in t else t for t in local_gov_terms[:6]
        )
        attack_clause = " OR ".join(
            f'"{t}"' if " " in t else t for t in attack_terms[:6]
        )
        queries.append(f'{pa_clause} AND ({gov_clause}) AND ({attack_clause})')

    # PA + specific incident types
    specific_combos = [
        '"municipal authority" OR "school district"',
        '"water authority" OR "sewer authority"',
        '"police department" OR "tax office"',
    ]
    core_attacks = "breach OR ransomware OR cyberattack"
    for combo in specific_combos:
        queries.append(f'({combo}) AND Pennsylvania AND ({core_attacks})')

    # General PA cybersecurity query
    queries.append(f'Pennsylvania cybersecurity incident breach ransomware')
    queries.append(f'Pennsylvania municipality cyberattack ransomware')

    return queries


def build_all_queries(session: Session, config: dict) -> dict[str, list[str]]:
    """Build all search queries, grouped by type.

    Returns:
        Dict with keys 'entity' and 'broad', each containing a list of query strings.
    """
    return {
        "entity": build_entity_queries(session, config),
        "broad": build_broad_queries(config),
    }
