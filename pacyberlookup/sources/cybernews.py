"""Cybersecurity news RSS sources: BleepingComputer, SecurityWeek, DataBreaches.net, Recorded Future.

These are Tier 1 sources — among the fastest outlets reporting ransomware events,
breach disclosures, and municipal cyber incidents.
"""

import re
from datetime import datetime, timezone

import atoma
import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_feed(content: bytes) -> list:
    """Parse RSS or Atom feed, returning a normalized list of item dicts."""
    items = []
    try:
        feed = atoma.parse_rss_bytes(content)
        for item in feed.items:
            items.append({
                "title": item.title or "",
                "link": item.link or "",
                "description": item.description or "",
                "published": item.pub_date,
            })
    except Exception:
        try:
            feed = atoma.parse_atom_bytes(content)
            for entry in feed.entries:
                title = entry.title
                if hasattr(title, "value"):
                    title = title.value
                link = ""
                if entry.links:
                    link = entry.links[0].href or ""
                summary = ""
                if entry.summary:
                    summary = str(entry.summary.value if hasattr(entry.summary, "value") else entry.summary)
                items.append({
                    "title": str(title or ""),
                    "link": link,
                    "description": summary,
                    "published": entry.published or entry.updated,
                })
        except Exception:
            pass
    return items


class BleepingComputerSource(BaseSource):
    """BleepingComputer RSS — one of the fastest outlets for ransomware reporting.

    Many attacks show up here before mainstream news. Covers:
    - Ransomware attacks
    - Data breaches
    - Law enforcement takedowns
    - Vulnerabilities exploited in the wild
    """

    FEED_URL = "https://www.bleepingcomputer.com/feed/"

    @property
    def source_name(self) -> str:
        return "BleepingComputer"

    @property
    def source_type(self) -> str:
        return "news"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        try:
            self.logger.info("Fetching BleepingComputer RSS")
            resp = requests.get(self.FEED_URL, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()

            items = _parse_rss_feed(resp.content)

            # Build keyword set from queries for relevance filtering
            keywords = self._extract_keywords(search_queries)

            for item in items:
                title = _clean_html(item["title"])
                desc = _clean_html(item["description"])
                combined = f"{title} {desc}".lower()

                if not any(kw in combined for kw in keywords):
                    continue

                published = item.get("published")
                if published and not isinstance(published, datetime):
                    try:
                        published = dateutil_parser.parse(str(published))
                    except (ValueError, TypeError):
                        published = None
                if published and published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)

                mentions.append(SourceMention(
                    headline=title,
                    source="BleepingComputer",
                    source_type="news",
                    url=item["link"],
                    raw_text=f"{title} {desc}",
                    published_at=published,
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching BleepingComputer feed")

        self.logger.info("BleepingComputer: found %d relevant mentions", len(mentions))
        return mentions

    def _extract_keywords(self, queries: list[str]) -> set[str]:
        keywords = set()
        for q in queries:
            for word in q.lower().replace('"', '').split():
                if len(word) > 3:
                    keywords.add(word)
        # Always include core cyber terms
        keywords.update(["breach", "ransomware", "cyberattack", "malware",
                         "pennsylvania", "municipality", "township", "borough"])
        return keywords


class SecurityWeekSource(BaseSource):
    """SecurityWeek RSS — enterprise breach and infrastructure attack reporting.

    Covers corporate breaches, infrastructure attacks, municipal ransomware,
    supply chain incidents. Includes technical detail useful for MSPs.
    """

    FEED_URL = "https://www.securityweek.com/feed/"

    @property
    def source_name(self) -> str:
        return "SecurityWeek"

    @property
    def source_type(self) -> str:
        return "news"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        try:
            self.logger.info("Fetching SecurityWeek RSS")
            resp = requests.get(self.FEED_URL, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()

            items = _parse_rss_feed(resp.content)
            keywords = self._extract_keywords(search_queries)

            for item in items:
                title = _clean_html(item["title"])
                desc = _clean_html(item["description"])
                combined = f"{title} {desc}".lower()

                if not any(kw in combined for kw in keywords):
                    continue

                published = item.get("published")
                if published and not isinstance(published, datetime):
                    try:
                        published = dateutil_parser.parse(str(published))
                    except (ValueError, TypeError):
                        published = None
                if published and published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)

                mentions.append(SourceMention(
                    headline=title,
                    source="SecurityWeek",
                    source_type="news",
                    url=item["link"],
                    raw_text=f"{title} {desc}",
                    published_at=published,
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching SecurityWeek feed")

        self.logger.info("SecurityWeek: found %d relevant mentions", len(mentions))
        return mentions

    def _extract_keywords(self, queries: list[str]) -> set[str]:
        keywords = set()
        for q in queries:
            for word in q.lower().replace('"', '').split():
                if len(word) > 3:
                    keywords.add(word)
        keywords.update(["breach", "ransomware", "cyberattack", "municipality",
                         "pennsylvania", "government", "municipal", "township"])
        return keywords


class DataBreachesNetSource(BaseSource):
    """DataBreaches.net RSS — long-tail breach tracking.

    Tracks hundreds of breaches not widely reported, including:
    - Ransomware leak claims
    - Breach disclosures
    - Investigations
    - Healthcare and municipal incidents
    """

    FEED_URL = "https://databreaches.net/feed/"

    @property
    def source_name(self) -> str:
        return "DataBreaches.net"

    @property
    def source_type(self) -> str:
        return "news"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        try:
            self.logger.info("Fetching DataBreaches.net RSS")
            resp = requests.get(self.FEED_URL, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()

            items = _parse_rss_feed(resp.content)
            keywords = self._extract_keywords(search_queries)

            for item in items:
                title = _clean_html(item["title"])
                desc = _clean_html(item["description"])
                combined = f"{title} {desc}".lower()

                if not any(kw in combined for kw in keywords):
                    continue

                published = item.get("published")
                if published and not isinstance(published, datetime):
                    try:
                        published = dateutil_parser.parse(str(published))
                    except (ValueError, TypeError):
                        published = None
                if published and published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)

                mentions.append(SourceMention(
                    headline=title,
                    source="DataBreaches.net",
                    source_type="news",
                    url=item["link"],
                    raw_text=f"{title} {desc}",
                    published_at=published,
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching DataBreaches.net feed")

        self.logger.info("DataBreaches.net: found %d relevant mentions", len(mentions))
        return mentions

    def _extract_keywords(self, queries: list[str]) -> set[str]:
        keywords = set()
        for q in queries:
            for word in q.lower().replace('"', '').split():
                if len(word) > 3:
                    keywords.add(word)
        keywords.update(["breach", "ransomware", "pennsylvania", "municipality",
                         "township", "borough", "healthcare", "hospital",
                         "school", "county", "authority"])
        return keywords


class RecordedFutureSource(BaseSource):
    """Recorded Future blog RSS — ransomware intelligence and context enrichment.

    Provides insights about ransomware groups, victim disclosures, and
    campaigns targeting local governments.
    """

    FEED_URL = "https://www.recordedfuture.com/feed"

    @property
    def source_name(self) -> str:
        return "Recorded Future"

    @property
    def source_type(self) -> str:
        return "news"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        try:
            self.logger.info("Fetching Recorded Future blog RSS")
            resp = requests.get(self.FEED_URL, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()

            items = _parse_rss_feed(resp.content)
            keywords = self._extract_keywords(search_queries)

            for item in items:
                title = _clean_html(item["title"])
                desc = _clean_html(item["description"])
                combined = f"{title} {desc}".lower()

                if not any(kw in combined for kw in keywords):
                    continue

                published = item.get("published")
                if published and not isinstance(published, datetime):
                    try:
                        published = dateutil_parser.parse(str(published))
                    except (ValueError, TypeError):
                        published = None
                if published and published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)

                mentions.append(SourceMention(
                    headline=title,
                    source="Recorded Future",
                    source_type="news",
                    url=item["link"],
                    raw_text=f"{title} {desc}",
                    published_at=published,
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching Recorded Future feed")

        self.logger.info("Recorded Future: found %d relevant mentions", len(mentions))
        return mentions

    def _extract_keywords(self, queries: list[str]) -> set[str]:
        keywords = set()
        for q in queries:
            for word in q.lower().replace('"', '').split():
                if len(word) > 3:
                    keywords.add(word)
        keywords.update(["ransomware", "breach", "government", "municipality",
                         "pennsylvania", "local", "lockbit", "blackcat",
                         "clop", "akira", "play"])
        return keywords
