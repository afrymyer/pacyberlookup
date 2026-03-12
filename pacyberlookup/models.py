"""SQLAlchemy data models for PA Cyber Incident Detection Feed."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Entity(Base):
    """Reference table of Pennsylvania organizations to monitor."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(String(255), nullable=False, unique=True)
    entity_type = Column(String(100), nullable=False)  # Municipality, School District, etc.
    county = Column(String(100))
    region = Column(String(100))
    website = Column(String(500))
    priority_tier = Column(Integer, default=2)  # 1=highest, 3=lowest
    is_client_or_prospect = Column(Boolean, default=False)
    watched = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    aliases = relationship("EntityAlias", back_populates="entity", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="entity")


class EntityAlias(Base):
    """Alternate names for entities (critical for matching inconsistent reporting)."""

    __tablename__ = "entity_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    alias = Column(String(255), nullable=False)

    entity = relationship("Entity", back_populates="aliases")


class RawMention(Base):
    """Raw source mention before scoring and deduplication."""

    __tablename__ = "raw_mentions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime)
    headline = Column(String(1000))
    source = Column(String(255))
    source_type = Column(String(50))  # news, gdelt, cisa, social
    url = Column(String(2000))
    raw_text = Column(Text)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Incident(Base):
    """Scored and categorized incident record (the main feed output)."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    entity_name = Column(String(255))
    matched_alias = Column(String(255))
    entity_type = Column(String(100))
    county = Column(String(100))
    headline = Column(String(1000))
    source = Column(String(255))
    source_type = Column(String(50))
    url = Column(String(2000))
    incident_type = Column(String(100))  # breach, ransomware, outage, etc.
    summary = Column(Text)
    confidence_score = Column(Float, default=0.0)
    confidence_band = Column(String(20))  # High, Medium, Low, Noise
    verification_status = Column(String(50), default="Unverified")
    category = Column(String(100))  # Confirmed Incident, Suspected Incident, etc.
    duplicate_group_id = Column(String(255))
    analyst_notes = Column(Text)
    requires_action = Column(Boolean, default=False)
    mapped_client_or_prospect = Column(Boolean, default=False)
    ai_summary = Column(Text)
    alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    entity = relationship("Entity", back_populates="incidents")
    source_mentions = relationship("IncidentSource", back_populates="incident",
                                   cascade="all, delete-orphan")


class IncidentSource(Base):
    """Links multiple source mentions to a single deduplicated incident."""

    __tablename__ = "incident_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    raw_mention_id = Column(Integer, ForeignKey("raw_mentions.id"), nullable=True)
    source = Column(String(255))
    source_type = Column(String(50))
    url = Column(String(2000))
    headline = Column(String(1000))
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="source_mentions")


def init_db(database_url: str = "sqlite:///data/pacyberlookup.db"):
    """Initialize the database and create all tables."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
