"""Have I Been Pwned (HIBP) domain monitoring.

Monitors client/prospect domains for breach indicators. HIBP tracks confirmed
data breaches globally and can provide early breach indicators when monitoring
specific domains.

API docs: https://haveibeenpwned.com/API/v3
Note: Domain search requires an HIBP API key (paid subscription).
"""

import logging
import os
from datetime import datetime, timezone

import requests

from .base import BaseSource, SourceMention

logger = logging.getLogger(__name__)


class HIBPSource(BaseSource):
    """Have I Been Pwned domain and breach monitoring.

    Checks monitored domains against the HIBP breach database.
    Also fetches recent breaches for PA-relevant keyword matching.
    """

    HIBP_BREACHES_URL = "https://haveibeenpwned.com/api/v3/breaches"
    HIBP_DOMAIN_URL = "https://haveibeenpwned.com/api/v3/breaches?domain={domain}"

    @property
    def source_name(self) -> str:
        return "Have I Been Pwned"

    @property
    def source_type(self) -> str:
        return "hibp"

    def _get_api_key(self) -> str:
        return os.getenv("HIBP_API_KEY", "")

    def _get_headers(self) -> dict:
        headers = {
            "User-Agent": "pacyberlookup/1.0",
        }
        api_key = self._get_api_key()
        if api_key:
            headers["hibp-api-key"] = api_key
        return headers

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch breach data from HIBP.

        Two modes:
        1. Domain monitoring: checks specific domains from entity config
        2. Recent breaches: scans recent breaches for PA-relevant keywords
        """
        mentions = []

        # Mode 1: Check monitored domains (requires API key)
        mentions.extend(self._check_monitored_domains())

        # Mode 2: Scan recent breaches for PA relevance (public API)
        mentions.extend(self._scan_recent_breaches(search_queries))

        self.logger.info("HIBP: found %d relevant mentions", len(mentions))
        return mentions

    def _check_monitored_domains(self) -> list[SourceMention]:
        """Check domains from the entity config against HIBP."""
        mentions = []
        api_key = self._get_api_key()
        if not api_key:
            self.logger.debug("No HIBP API key configured; skipping domain monitoring")
            return mentions

        # Get monitored domains from config
        domains = self.config.get("hibp", {}).get("monitored_domains", [])
        if not domains:
            return mentions

        for domain in domains:
            try:
                self.logger.info("Checking HIBP for domain: %s", domain)
                resp = requests.get(
                    self.HIBP_DOMAIN_URL.format(domain=domain),
                    headers=self._get_headers(),
                    timeout=15,
                )
                if resp.status_code == 404:
                    continue  # No breaches found for this domain
                resp.raise_for_status()

                breaches = resp.json()
                for breach in breaches:
                    name = breach.get("Name", "")
                    title = breach.get("Title", name)
                    breach_date = breach.get("BreachDate", "")
                    description = breach.get("Description", "")
                    data_classes = breach.get("DataClasses", [])

                    published = None
                    if breach_date:
                        try:
                            published = datetime.strptime(breach_date, "%Y-%m-%d").replace(
                                tzinfo=timezone.utc
                            )
                        except ValueError:
                            pass

                    data_types = ", ".join(data_classes[:5]) if data_classes else "unknown"
                    headline = f"HIBP: {title} breach affects domain {domain}"
                    raw_text = (
                        f"{headline}. Exposed data: {data_types}. {description}"
                    )

                    mentions.append(SourceMention(
                        headline=headline,
                        source="Have I Been Pwned",
                        source_type="hibp",
                        url=f"https://haveibeenpwned.com/api/v3/breach/{name}",
                        raw_text=raw_text[:2000],
                        published_at=published,
                        source_credibility="national_news",
                    ))
            except Exception:
                self.logger.exception("Error checking HIBP for domain: %s", domain)

        return mentions

    def _scan_recent_breaches(self, search_queries: list[str]) -> list[SourceMention]:
        """Scan the full HIBP breach list for PA-relevant entries."""
        mentions = []
        try:
            self.logger.info("Fetching HIBP breach catalog")
            resp = requests.get(
                self.HIBP_BREACHES_URL,
                headers={"User-Agent": "pacyberlookup/1.0"},
                timeout=30,
            )
            resp.raise_for_status()
            breaches = resp.json()

            # Build keyword set for matching
            keywords = set()
            for q in search_queries:
                for word in q.lower().replace('"', '').split():
                    if len(word) > 3:
                        keywords.add(word)
            keywords.update(["pennsylvania", "municipality", "township",
                             "borough", "county", "government"])

            # Only scan recent breaches (last 50 or those from current year)
            recent = breaches[-50:] if len(breaches) > 50 else breaches

            for breach in recent:
                name = breach.get("Name", "")
                title = breach.get("Title", name)
                description = breach.get("Description", "")
                domain = breach.get("Domain", "")
                breach_date = breach.get("BreachDate", "")
                combined = f"{title} {description} {domain}".lower()

                if not any(kw in combined for kw in keywords):
                    continue

                published = None
                if breach_date:
                    try:
                        published = datetime.strptime(breach_date, "%Y-%m-%d").replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        pass

                data_classes = breach.get("DataClasses", [])
                data_types = ", ".join(data_classes[:5]) if data_classes else "unknown"

                mentions.append(SourceMention(
                    headline=f"HIBP Breach: {title}",
                    source="Have I Been Pwned",
                    source_type="hibp",
                    url=f"https://haveibeenpwned.com/api/v3/breach/{name}",
                    raw_text=f"{title}. Domain: {domain}. Exposed: {data_types}. {description}"[:2000],
                    published_at=published,
                    source_credibility="national_news",
                ))
        except Exception:
            self.logger.exception("Error fetching HIBP breach catalog")

        return mentions
