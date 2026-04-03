"""Flask web application for real-time voting on technical recommendations."""

import json
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..models import Base, Incident
from ..utils.config import get_database_url, load_env
from .models import Recommendation, Vote

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> Flask:
    """Create and configure the Flask voting application."""
    load_env()

    if database_url is None:
        database_url = get_database_url()

    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SESSION_FACTORY"] = Session

    def get_session():
        return app.config["SESSION_FACTORY"]()

    # ── Pages ──────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        """Main voting board."""
        return render_template("voting.html")

    # ── API: Recommendations ───────────────────────────────────────────

    @app.route("/api/recommendations", methods=["GET"])
    def list_recommendations():
        """List all recommendations with vote counts."""
        session = get_session()
        try:
            status_filter = request.args.get("status", "all")
            query = session.query(Recommendation).order_by(
                Recommendation.created_at.desc()
            )
            if status_filter != "all":
                query = query.filter(Recommendation.status == status_filter)

            recs = query.all()
            result = []
            for r in recs:
                result.append({
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "category": r.category,
                    "priority": r.priority,
                    "status": r.status,
                    "submitted_by": r.submitted_by,
                    "incident_id": r.incident_id,
                    "approve_count": r.approve_count,
                    "reject_count": r.reject_count,
                    "total_votes": r.total_votes,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "votes": [
                        {
                            "voter_name": v.voter_name,
                            "vote_value": v.vote_value,
                            "comment": v.comment,
                            "created_at": v.created_at.isoformat() if v.created_at else None,
                        }
                        for v in r.votes
                    ],
                })
            return jsonify(result)
        finally:
            session.close()

    @app.route("/api/recommendations", methods=["POST"])
    def create_recommendation():
        """Create a new recommendation."""
        session = get_session()
        try:
            data = request.get_json()
            if not data or not data.get("title") or not data.get("description"):
                return jsonify({"error": "title and description are required"}), 400

            rec = Recommendation(
                title=data["title"],
                description=data["description"],
                category=data.get("category", "General"),
                priority=data.get("priority", "Medium"),
                submitted_by=data.get("submitted_by", "Anonymous"),
                incident_id=data.get("incident_id"),
            )
            session.add(rec)
            session.commit()

            return jsonify({
                "id": rec.id,
                "title": rec.title,
                "message": "Recommendation created",
            }), 201
        except Exception as e:
            session.rollback()
            logger.error("Failed to create recommendation: %s", e)
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    # ── API: Voting ────────────────────────────────────────────────────

    @app.route("/api/recommendations/<int:rec_id>/vote", methods=["POST"])
    def cast_vote(rec_id):
        """Cast a vote (approve/reject) on a recommendation."""
        session = get_session()
        try:
            data = request.get_json()
            vote_value = data.get("vote") if data else None
            if vote_value not in ("approve", "reject"):
                return jsonify({"error": "vote must be 'approve' or 'reject'"}), 400

            rec = session.get(Recommendation, rec_id)
            if not rec:
                return jsonify({"error": "Recommendation not found"}), 404

            voter_name = data.get("voter_name", "Anonymous")

            # Check if this voter already voted on this recommendation
            existing = session.query(Vote).filter_by(
                recommendation_id=rec_id, voter_name=voter_name
            ).first()

            if existing:
                # Update existing vote
                existing.vote_value = vote_value
                existing.comment = data.get("comment")
                existing.created_at = datetime.now(timezone.utc)
            else:
                vote = Vote(
                    recommendation_id=rec_id,
                    voter_name=voter_name,
                    vote_value=vote_value,
                    comment=data.get("comment"),
                )
                session.add(vote)

            session.commit()

            # Refresh to get updated counts
            session.refresh(rec)
            return jsonify({
                "message": "Vote recorded",
                "approve_count": rec.approve_count,
                "reject_count": rec.reject_count,
                "total_votes": rec.total_votes,
            })
        except Exception as e:
            session.rollback()
            logger.error("Failed to cast vote: %s", e)
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    # ── API: Update status ─────────────────────────────────────────────

    @app.route("/api/recommendations/<int:rec_id>/status", methods=["PATCH"])
    def update_status(rec_id):
        """Update the status of a recommendation."""
        session = get_session()
        try:
            data = request.get_json()
            new_status = data.get("status") if data else None
            if new_status not in ("Open", "Approved", "Rejected", "Deferred"):
                return jsonify({"error": "Invalid status"}), 400

            rec = session.get(Recommendation, rec_id)
            if not rec:
                return jsonify({"error": "Recommendation not found"}), 404

            rec.status = new_status
            session.commit()

            return jsonify({"message": f"Status updated to {new_status}"})
        except Exception as e:
            session.rollback()
            logger.error("Failed to update status: %s", e)
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    # ── API: Import incidents as recommendations ───────────────────────

    @app.route("/api/import-incidents", methods=["POST"])
    def import_incidents():
        """Import unreviewed incidents as recommendations for voting."""
        session = get_session()
        try:
            incidents = session.query(Incident).filter(
                Incident.verification_status == "Unverified"
            ).order_by(Incident.detected_at.desc()).limit(50).all()

            imported = 0
            for inc in incidents:
                # Skip if already imported
                existing = session.query(Recommendation).filter_by(
                    incident_id=inc.id
                ).first()
                if existing:
                    continue

                rec = Recommendation(
                    title=inc.headline or f"Incident #{inc.id}: {inc.incident_type}",
                    description=(
                        f"Entity: {inc.entity_name or 'Unknown'}\n"
                        f"Type: {inc.incident_type or 'Unknown'}\n"
                        f"Source: {inc.source or 'Unknown'}\n"
                        f"Confidence: {inc.confidence_band} ({inc.confidence_score})\n"
                        f"Summary: {inc.summary or inc.ai_summary or 'No summary available'}"
                    ),
                    category=inc.category or "Incident Review",
                    priority=_confidence_to_priority(inc.confidence_band),
                    submitted_by="System Import",
                    incident_id=inc.id,
                )
                session.add(rec)
                imported += 1

            session.commit()
            return jsonify({"message": f"Imported {imported} incidents as recommendations"})
        except Exception as e:
            session.rollback()
            logger.error("Failed to import incidents: %s", e)
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    return app


def _confidence_to_priority(band: str | None) -> str:
    """Map incident confidence band to recommendation priority."""
    mapping = {
        "High": "Critical",
        "Medium": "High",
        "Low": "Medium",
        "Noise": "Low",
    }
    return mapping.get(band, "Medium")


def run_voting_app(host: str = "0.0.0.0", port: int = 5050, debug: bool = False):
    """Launch the voting recommendations web app."""
    app = create_app()
    print(f"\n  Voting Recommendations App")
    print(f"  {'=' * 40}")
    print(f"  Running at: http://{host}:{port}")
    print(f"  Vote green (approve) or red (reject)")
    print(f"  {'=' * 40}\n")
    app.run(host=host, port=port, debug=debug)
