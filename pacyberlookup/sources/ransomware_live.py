"""Ransomware.live — ransomware leak site monitor.

Tracks ransomware gangs posting victims on leak sites. Monitors groups like
LockBit, BlackCat/ALPHV, Cl0p, Akira, Play, and others.

Sometimes victims appear on leak sites weeks before public disclosure.
API: https://www.ransomware.live/
"""

from datetime import datetime, timezone

import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class RansomwareLiveSource(BaseSource):
    """Monitor ransomware.live for victim postings relevant to PA organizations.

    Fetches recent victim posts from ransomware group leak sites and
    filters for Pennsylvania-relevant entities.
    """

    # ransomware.live public API endpoints
    RECENT_VICTIMS_URL = "https://api.ransomware.live/recentvictims"
    ALL_VICTIMS_URL = "https://api.ransomware.live/victims"

    @property
    def source_name(self) -> str:
        return "Ransomware.live"

    @property
    def source_type(self) -> str:
        return "ransomware_leak"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        mentions.extend(self._fetch_recent_victims(search_queries))
        self.logger.info("Ransomware.live: found %d relevant mentions", len(mentions))
        return mentions

    def _fetch_recent_victims(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch recent ransomware victim postings."""
        mentions = []
        try:
            self.logger.info("Fetching Ransomware.live recent victims")
            resp = requests.get(
                self.RECENT_VICTIMS_URL,
                timeout=30,
                headers={"User-Agent": "pacyberlookup/1.0"},
            )
            resp.raise_for_status()
            victims = resp.json()

            # Build keyword set for matching
            keywords = set()
            for q in search_queries:
                for word in q.lower().replace('"', '').split():
                    if len(word) > 3:
                        keywords.add(word)
            # Always include PA-relevant terms
            keywords.update([
                "pennsylvania", "township", "borough", "municipality",
                "county", "authority", "school", "hospital", "health",
            ])

            for victim in victims:
                victim_name = victim.get("post_title", "") or victim.get("victim", "")
                group_name = victim.get("group_name", "Unknown")
                discovered = victim.get("discovered", "") or victim.get("date", "")
                description = victim.get("description", "")
                website = victim.get("website", "")
                country = victim.get("country", "")

                # Filter: check for PA relevance in victim name, description, or website
                combined = f"{victim_name} {description} {website} {country}".lower()
                if not any(kw in combined for kw in keywords):
                    continue

                published = None
                if discovered:
                    try:
                        published = dateutil_parser.parse(discovered)
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                headline = f"Ransomware Leak: {group_name} posted {victim_name}"
                raw_text = (
                    f"Ransomware group {group_name} posted victim: {victim_name}. "
                    f"Website: {website}. {description}"
                )

                mentions.append(SourceMention(
                    headline=headline,
                    source=f"Ransomware.live ({group_name})",
                    source_type="ransomware_leak",
                    url=f"https://www.ransomware.live",
                    raw_text=raw_text[:2000],
                    published_at=published,
                    # Leak site postings are highly credible for confirming ransomware
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching Ransomware.live victims")

        return mentions
