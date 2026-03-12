"""Tests for search query builder."""

from pacyberlookup.models import Base, Entity, EntityAlias, init_db
from pacyberlookup.search import build_all_queries, build_broad_queries, build_entity_queries
from pacyberlookup.utils.config import load_config


def _setup_test_db():
    """Create an in-memory test database with sample entities."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    entity = Entity(
        entity_name="Lower Swatara Township",
        entity_type="Municipality",
        county="Dauphin",
        watched=True,
    )
    session.add(entity)
    session.flush()

    session.add(EntityAlias(entity_id=entity.id, alias="Lower Swatara Twp"))
    session.add(EntityAlias(entity_id=entity.id, alias="Lower Swatara"))

    entity2 = Entity(
        entity_name="Derry Township School District",
        entity_type="School District",
        county="Dauphin",
        watched=True,
    )
    session.add(entity2)
    session.flush()
    session.add(EntityAlias(entity_id=entity2.id, alias="Derry Twp SD"))

    session.commit()
    return session


def test_build_entity_queries():
    session = _setup_test_db()
    config = load_config()
    queries = build_entity_queries(session, config)

    assert len(queries) > 0
    # Should include entity name queries
    assert any("Lower Swatara Township" in q for q in queries)
    # Should include alias queries
    assert any("Lower Swatara Twp" in q for q in queries)
    # Should include incident keywords
    assert any("breach" in q.lower() for q in queries)


def test_build_broad_queries():
    config = load_config()
    queries = build_broad_queries(config)

    assert len(queries) > 0
    # Should include PA qualifiers
    assert any("pennsylvania" in q.lower() for q in queries)
    # Should include incident keywords
    assert any("breach" in q.lower() or "ransomware" in q.lower() for q in queries)


def test_build_all_queries():
    session = _setup_test_db()
    config = load_config()
    result = build_all_queries(session, config)

    assert "entity" in result
    assert "broad" in result
    assert len(result["entity"]) > 0
    assert len(result["broad"]) > 0
