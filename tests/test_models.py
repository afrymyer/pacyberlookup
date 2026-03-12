"""Tests for database models."""

from pacyberlookup.models import Base, Entity, EntityAlias, Incident, init_db


def test_init_db_memory():
    """Test database initialization with in-memory SQLite."""
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()

    # Should be able to create and query entities
    entity = Entity(
        entity_name="Test Township",
        entity_type="Municipality",
        county="Test County",
    )
    session.add(entity)
    session.commit()

    result = session.query(Entity).first()
    assert result is not None
    assert result.entity_name == "Test Township"
    session.close()


def test_entity_alias_relationship():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()

    entity = Entity(entity_name="Test Borough", entity_type="Municipality")
    session.add(entity)
    session.flush()

    alias = EntityAlias(entity_id=entity.id, alias="Test Boro")
    session.add(alias)
    session.commit()

    result = session.query(Entity).first()
    assert len(result.aliases) == 1
    assert result.aliases[0].alias == "Test Boro"
    session.close()


def test_incident_entity_relationship():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()

    entity = Entity(entity_name="Test SD", entity_type="School District")
    session.add(entity)
    session.flush()

    incident = Incident(
        entity_id=entity.id,
        entity_name="Test SD",
        headline="Test breach",
        confidence_score=75.0,
        confidence_band="High",
    )
    session.add(incident)
    session.commit()

    result = session.query(Entity).first()
    assert len(result.incidents) == 1
    assert result.incidents[0].confidence_score == 75.0
    session.close()
