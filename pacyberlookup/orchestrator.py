"""Main orchestrator for the PA Cyber Incident Detection Feed.

Coordinates the full pipeline:
1. Build search queries from entity list + config
2. Fetch mentions from all sources (with health tracking)
3. Match mentions to entities (with geo enrichment)
4. Score confidence
5. Deduplicate
6. Summarize
7. Persist to database (with timeline tracking)
8. Route alerts (Teams, email, SharePoint, watchlist)
9. Export for Power BI
"""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .geo import enrich_county
from .health import SourceHealthTracker
from .models import Entity, EntityAlias, Incident, IncidentSource, RawMention
from .scoring.confidence import ConfidenceScorer
from .scoring.dedup import deduplicate_mentions
from .scoring.summarizer import summarize_incident
from .search import build_all_queries
from .sources.base import BaseSource, SourceMention
from .sources.cisa import CISASource
from .sources.cybernews import (
    BleepingComputerSource,
    DataBreachesNetSource,
    RecordedFutureSource,
    SecurityWeekSource,
)
from .sources.gdelt import GDELTSource
from .sources.hibp import HIBPSource
from .sources.news import GoogleNewsSource
from .sources.otx import OTXSource
from .sources.pa_attorney_general import PAAttorneyGeneralSource
from .sources.ransomware_live import RansomwareLiveSource
from .sources.shadowserver import ShadowserverSource
from .sources.social import RedditSource
from .timeline import auto_update_timeline
from .utils.text import extract_incident_type, normalize_text

logger = logging.getLogger(__name__)


class FeedOrchestrator:
    """Runs one full cycle of the incident detection feed."""

    def __init__(self, session: Session, config: dict):
        self.session = session
        self.config = config
        self.scorer = ConfidenceScorer(config)
        self.health_tracker = SourceHealthTracker(session)

        # Initialize sources — layered model
        # Tier 1: High-confidence public sources
        self.sources: list[BaseSource] = [
            GoogleNewsSource(config),          # Google News RSS
            BleepingComputerSource(config),    # Fast ransomware reporting
            SecurityWeekSource(config),        # Enterprise breach news
            DataBreachesNetSource(config),     # Long-tail breach tracking
            RecordedFutureSource(config),      # Ransomware intelligence
            CISASource(config),                # CISA alerts + KEV
            HIBPSource(config),                # Have I Been Pwned breach DB
            PAAttorneyGeneralSource(config),   # PA AG breach notices
        ]
        # Tier 2: Broad discovery
        self.sources += [
            GDELTSource(config),               # Global news every ~15 min
            RansomwareLiveSource(config),       # Ransomware leak site monitor
        ]
        # Tier 3: Threat intelligence / enrichment
        self.sources += [
            OTXSource(config),                 # AlienVault OTX pulses
            ShadowserverSource(config),        # Internet exposure alerts
        ]
        # Tier 4: Social / chatter (signals only)
        self.sources += [
            RedditSource(config),              # Reddit social monitoring
        ]

    def run_cycle(self, source_filter: list[str] | None = None) -> list[dict]:
        """Execute one full detection cycle.

        Args:
            source_filter: Optional list of source_type strings to poll.
                           If None, polls all sources.

        Returns:
            List of new/updated incident dicts that were processed.
        """
        logger.info("=== Starting feed cycle at %s ===", datetime.now(timezone.utc))

        # 1. Build queries
        queries = build_all_queries(self.session, self.config)
        all_queries = queries.get("entity", []) + queries.get("broad", [])
        logger.info("Built %d search queries (%d entity, %d broad)",
                     len(all_queries), len(queries.get("entity", [])),
                     len(queries.get("broad", [])))

        if not all_queries:
            logger.warning("No search queries generated (no watched entities?)")
            return []

        # 2. Fetch from sources (with health tracking)
        sources_to_poll = self.sources
        if source_filter:
            sources_to_poll = [s for s in self.sources if s.source_type in source_filter]

        all_mentions: list[SourceMention] = []
        for source in sources_to_poll:
            start_time = time.monotonic()
            try:
                mentions = source.fetch_with_retry(all_queries)
                duration = (time.monotonic() - start_time) * 1000
                all_mentions.extend(mentions)
                logger.info("Source %s returned %d mentions (%.0fms)",
                            source.source_name, len(mentions), duration)

                # Record health
                status = "ok" if mentions else "empty"
                self.health_tracker.record(
                    source.source_name, source.source_type,
                    status, len(mentions), duration,
                )
            except Exception as e:
                duration = (time.monotonic() - start_time) * 1000
                logger.exception("Source %s failed", source.source_name)
                self.health_tracker.record(
                    source.source_name, source.source_type,
                    "error", 0, duration, str(e),
                )

        # Check for failing sources and warn
        failing = self.health_tracker.get_failing_sources(min_consecutive=3)
        for f in failing:
            logger.warning(
                "SOURCE HEALTH WARNING: %s has failed %d consecutive cycles. "
                "Last error: %s",
                f["source_name"], f["consecutive_failures"], f["last_error_message"],
            )

        logger.info("Total raw mentions: %d", len(all_mentions))
        if not all_mentions:
            logger.info("No mentions found this cycle")
            return []

        # 3. Persist raw mentions
        self._persist_raw_mentions(all_mentions)

        # 4. Match entities and score (with geo enrichment)
        scored = self._match_and_score(all_mentions)
        logger.info("Scored %d mentions", len(scored))

        # 5. Deduplicate
        deduped = deduplicate_mentions(scored)
        logger.info("Deduplicated to %d incidents", len(deduped))

        # 6. Re-score with cross-source validation
        for incident in deduped:
            source_count = incident.get("source_count", 1)
            cross_score = self.scorer.score_cross_source(source_count)
            incident["confidence_score"] = min(
                100, incident["confidence_score"] + cross_score
            )
            incident["confidence_band"] = self.scorer.get_band(
                incident["confidence_score"]
            )
            incident["category"] = self.scorer.get_category(
                incident["confidence_score"], incident.get("source_type", "")
            )

        # 7. Summarize
        for incident in deduped:
            incident["ai_summary"] = summarize_incident(incident)

        # 8. Persist incidents (with timeline tracking)
        self._persist_incidents(deduped)

        # 9. Route alerts (with watchlist priority)
        new_alerts = [i for i in deduped if i.get("confidence_band") in ("High", "Medium")]
        self._route_alerts(new_alerts)

        logger.info("=== Cycle complete: %d incidents, %d alerts ===",
                     len(deduped), len(new_alerts))
        return deduped

    def _persist_raw_mentions(self, mentions: list[SourceMention]) -> list[int]:
        """Save raw mentions to database."""
        ids = []
        for m in mentions:
            raw = RawMention(
                detected_at=m.detected_at,
                published_at=m.published_at,
                headline=m.headline[:1000] if m.headline else "",
                source=m.source,
                source_type=m.source_type,
                url=m.url,
                raw_text=m.raw_text,
            )
            self.session.add(raw)
            self.session.flush()
            ids.append(raw.id)
        self.session.commit()
        return ids

    def _match_and_score(self, mentions: list[SourceMention]) -> list[dict]:
        """Match mentions against entities and compute confidence scores."""
        entities = self.session.query(Entity).filter(Entity.watched.is_(True)).all()

        # Build entity lookup
        entity_data = []
        for e in entities:
            aliases = [a.alias for a in e.aliases]
            entity_data.append({
                "entity": e,
                "name": e.entity_name,
                "aliases": aliases,
            })

        scored = []
        for mention in mentions:
            best_score = None
            best_entity = None

            for ed in entity_data:
                result = self.scorer.compute_total_score(
                    mention,
                    entity_name=ed["name"],
                    aliases=ed["aliases"],
                    source_count=1,
                )
                if best_score is None or result["total"] > best_score["total"]:
                    best_score = result
                    best_entity = ed

            # If no entity match found, still score on source + language alone
            if best_score is None or best_score["entity_match"] == 0:
                result = self.scorer.compute_total_score(mention)
                if best_score is None or result["total"] > best_score["total"]:
                    best_score = result
                    best_entity = None

            entity = best_entity["entity"] if best_entity and best_score["entity_match"] > 0 else None
            incident_type = extract_incident_type(
                f"{mention.headline} {mention.raw_text}"
            )

            # Geo enrichment: if no entity match, try to identify county from text
            county = entity.county if entity else ""
            if not county:
                county = enrich_county(f"{mention.headline} {mention.raw_text}") or ""

            scored_item = {
                "detected_at": mention.detected_at,
                "published_at": mention.published_at,
                "entity_id": entity.id if entity else None,
                "entity_name": entity.entity_name if entity else "",
                "matched_alias": best_score.get("matched_alias", ""),
                "entity_type": entity.entity_type if entity else "",
                "county": county,
                "headline": mention.headline,
                "source": mention.source,
                "source_type": mention.source_type,
                "source_credibility": mention.source_credibility,
                "url": mention.url,
                "raw_text": mention.raw_text,
                "incident_type": incident_type or "unknown",
                "confidence_score": best_score["total"],
                "confidence_band": best_score["confidence_band"],
                "category": self.scorer.get_category(
                    best_score["total"], mention.source_type
                ),
                "is_client_or_prospect": entity.is_client_or_prospect if entity else False,
            }
            scored.append(scored_item)

        return scored

    def _persist_incidents(self, incidents: list[dict]):
        """Save deduplicated incidents to the database with timeline tracking."""
        for inc in incidents:
            # Check if this dedup group already exists
            existing = None
            dedup_id = inc.get("duplicate_group_id", "")
            if dedup_id:
                existing = self.session.query(Incident).filter(
                    Incident.duplicate_group_id == dedup_id
                ).first()

            if existing:
                # Update existing incident if new score is higher
                if inc["confidence_score"] > (existing.confidence_score or 0):
                    existing.confidence_score = inc["confidence_score"]
                    existing.confidence_band = inc["confidence_band"]
                    existing.category = inc["category"]
                    existing.ai_summary = inc.get("ai_summary", "")
                    existing.updated_at = datetime.now(timezone.utc)
                inc["db_id"] = existing.id

                # Update timeline
                try:
                    auto_update_timeline(
                        self.session, existing.id,
                        inc.get("source_count", 1),
                    )
                except Exception:
                    logger.debug("Timeline update skipped for incident %d", existing.id)
            else:
                incident_obj = Incident(
                    detected_at=inc.get("detected_at"),
                    published_at=inc.get("published_at"),
                    entity_id=inc.get("entity_id"),
                    entity_name=inc.get("entity_name", ""),
                    matched_alias=inc.get("matched_alias", ""),
                    entity_type=inc.get("entity_type", ""),
                    county=inc.get("county", ""),
                    headline=inc.get("headline", "")[:1000],
                    source=inc.get("source", ""),
                    source_type=inc.get("source_type", ""),
                    url=inc.get("url", ""),
                    incident_type=inc.get("incident_type", ""),
                    summary=inc.get("ai_summary", ""),
                    confidence_score=inc.get("confidence_score", 0),
                    confidence_band=inc.get("confidence_band", ""),
                    category=inc.get("category", ""),
                    verification_status="Unverified",
                    duplicate_group_id=inc.get("duplicate_group_id", ""),
                    requires_action=inc.get("confidence_band") in ("High", "Medium"),
                    mapped_client_or_prospect=inc.get("is_client_or_prospect", False),
                    ai_summary=inc.get("ai_summary", ""),
                )
                self.session.add(incident_obj)
                self.session.flush()
                inc["db_id"] = incident_obj.id

                # Add source mentions
                for sm in inc.get("source_mentions", []):
                    src = IncidentSource(
                        incident_id=incident_obj.id,
                        source=sm.get("source", ""),
                        source_type=sm.get("source_type", ""),
                        url=sm.get("url", ""),
                        headline=sm.get("headline", "")[:1000],
                        published_at=sm.get("published_at"),
                    )
                    self.session.add(src)

                # Create initial timeline event
                try:
                    auto_update_timeline(
                        self.session, incident_obj.id,
                        inc.get("source_count", 1),
                    )
                except Exception:
                    logger.debug("Timeline creation skipped for incident %d", incident_obj.id)

        self.session.commit()

    def _route_alerts(self, incidents: list[dict]):
        """Route high/medium confidence incidents to Teams, email, SharePoint.

        Client/prospect incidents get additional watchlist routing with
        auto-generated talking points.
        """
        from .alerts.teams import send_teams_alert
        from .alerts.sharepoint import push_to_sharepoint
        from .alerts.watchlist import send_watchlist_alert

        for inc in incidents:
            # Standard Teams alert
            try:
                send_teams_alert(inc)
            except Exception:
                logger.exception("Teams alert failed for %s", inc.get("entity_name"))

            # SharePoint
            try:
                push_to_sharepoint(inc)
            except Exception:
                logger.exception("SharePoint push failed for %s", inc.get("entity_name"))

            # Watchlist: client/prospect incidents get priority routing
            if inc.get("is_client_or_prospect"):
                try:
                    send_watchlist_alert(inc)
                except Exception:
                    logger.exception(
                        "Watchlist alert failed for %s", inc.get("entity_name")
                    )
