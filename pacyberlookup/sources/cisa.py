"""CISA cyber alerts, advisories, and KEV ingestion for enrichment context."""

from datetime import datetime, timezone

import atoma
import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class CISASource(BaseSource):
    """Fetch CISA alerts, advisories, and KEV catalog entries.

    CISA publishes RSS feeds for alerts and advisories. The KEV (Known
    Exploited Vulnerabilities) catalog is a JSON endpoint. These are used
    primarily for enrichment and risk context rather than victim identification.
    """

    CISA_ALERTS_RSS = "https://www.cisa.gov/cybersecurity-advisories/all.xml"
    CISA_KEV_JSON = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    @property
    def source_name(self) -> str:
        return "CISA"

    @property
    def source_type(self) -> str:
        return "cisa"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch CISA alerts/advisories. search_queries are used to filter relevance."""
        mentions = []
        mentions.extend(self._fetch_alerts(search_queries))
        mentions.extend(self._fetch_kev(search_queries))
        self.logger.info("CISA: found %d relevant mentions", len(mentions))
        return mentions

    def _fetch_alerts(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch and filter CISA RSS alerts/advisories."""
        mentions = []
        try:
            self.logger.info("Fetching CISA alerts RSS")
            resp = requests.get(self.CISA_ALERTS_RSS, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()

            # Build keyword set from queries for relevance filtering
            keywords = set()
            for q in search_queries:
                for word in q.lower().split():
                    if len(word) > 3:
                        keywords.add(word)

            # Parse RSS or Atom
            try:
                feed = atoma.parse_rss_bytes(resp.content)
                items = feed.items[:100]
            except Exception:
                feed = atoma.parse_atom_bytes(resp.content)
                items = feed.entries[:100]

            for item in items:
                title = getattr(item, "title", "") or ""
                if hasattr(title, "value"):
                    title = title.value
                title = str(title)

                description = ""
                if hasattr(item, "description") and item.description:
                    description = str(item.description)
                elif hasattr(item, "summary") and item.summary:
                    description = str(item.summary)

                link = ""
                if hasattr(item, "link") and item.link:
                    link = str(item.link)
                elif hasattr(item, "links") and item.links:
                    link = item.links[0].href or ""

                combined_text = f"{title} {description}".lower()

                relevant = any(kw in combined_text for kw in keywords)
                if not relevant:
                    continue

                published = None
                pub = getattr(item, "pub_date", None) or getattr(item, "published", None) or getattr(item, "updated", None)
                if pub:
                    if isinstance(pub, datetime):
                        published = pub if pub.tzinfo else pub.replace(tzinfo=timezone.utc)
                    else:
                        try:
                            published = dateutil_parser.parse(str(pub))
                            if published.tzinfo is None:
                                published = published.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                mentions.append(SourceMention(
                    headline=title,
                    source="CISA",
                    source_type="cisa",
                    url=link,
                    raw_text=f"{title} {description}",
                    published_at=published,
                    source_credibility="government_advisory",
                ))
        except Exception:
            self.logger.exception("Error fetching CISA alerts RSS")

        return mentions

    def _fetch_kev(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch recent KEV entries for enrichment context."""
        mentions = []
        try:
            self.logger.info("Fetching CISA KEV catalog")
            resp = requests.get(self.CISA_KEV_JSON, timeout=30, headers={
                "User-Agent": "pacyberlookup/1.0"
            })
            resp.raise_for_status()
            data = resp.json()

            vulnerabilities = data.get("vulnerabilities", [])
            # Only look at the most recent entries (last 20)
            recent = vulnerabilities[-20:] if len(vulnerabilities) > 20 else vulnerabilities

            keywords = set()
            for q in search_queries:
                for word in q.lower().split():
                    if len(word) > 3:
                        keywords.add(word)

            for vuln in recent:
                name = vuln.get("vulnerabilityName", "")
                vendor = vuln.get("vendorProject", "")
                product = vuln.get("product", "")
                description = vuln.get("shortDescription", "")
                cve = vuln.get("cveID", "")
                combined = f"{name} {vendor} {product} {description}".lower()

                relevant = any(kw in combined for kw in keywords)
                if not relevant:
                    continue

                due_date = vuln.get("dueDate", "")
                published = None
                if due_date:
                    try:
                        published = dateutil_parser.parse(due_date)
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                mentions.append(SourceMention(
                    headline=f"KEV: {cve} - {name} ({vendor} {product})",
                    source="CISA KEV",
                    source_type="cisa",
                    url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                    raw_text=f"{name} {description}",
                    published_at=published,
                    source_credibility="government_advisory",
                ))
        except Exception:
            self.logger.exception("Error fetching CISA KEV catalog")

        return mentions
