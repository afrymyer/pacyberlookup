"""Data models for the voting recommendations system."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..models import Base


class Recommendation(Base):
    """A technical recommendation that team members can vote on."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), default="General")
    priority = Column(String(20), default="Medium")  # Low, Medium, High, Critical
    status = Column(String(20), default="Open")  # Open, Approved, Rejected, Deferred
    submitted_by = Column(String(255), default="Anonymous")
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    votes = relationship("Vote", back_populates="recommendation",
                         cascade="all, delete-orphan")

    @property
    def approve_count(self):
        return sum(1 for v in self.votes if v.vote_value == "approve")

    @property
    def reject_count(self):
        return sum(1 for v in self.votes if v.vote_value == "reject")

    @property
    def total_votes(self):
        return len(self.votes)


class Vote(Base):
    """A vote on a recommendation (approve=green, reject=red)."""

    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    voter_name = Column(String(255), default="Anonymous")
    vote_value = Column(String(10), nullable=False)  # "approve" or "reject"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    recommendation = relationship("Recommendation", back_populates="votes")
