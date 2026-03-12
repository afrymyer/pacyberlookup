"""AlienVault Open Threat Exchange (OTX) threat intelligence.

OTX provides community-sourced threat intelligence including:
- Malicious indicators (IPs, domains, hashes)
- Attack campaigns ("pulses")
- Infrastructure used in attacks

Cross-reference indicators with incidents your feed detects for enrichment.
API docs: https://otx.alienvault.com/api
"""

import os
from datetime import datetime, timezone

import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class OTXSource(BaseSource):
    """AlienVault OTX pulse and threat intelligence monitoring.

    Fetches recent OTX pulses (threat reports) and filters for
    PA-relevant threat intelligence.
    """

    OTX_PULSES_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"
    OTX_SEARCH_URL = "https://otx.alienvault.com/api/v1/search/pulses"

    @property
    def source_name(self) -> str:
        return "AlienVault OTX"

    @property
    def source_type(self) -> str:
        return "threat_intel"

    def _get_api_key(self) -> str:
        return os.getenv("OTX_API_KEY", "")

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []

        api_key = self._get_api_key()
        if not api_key:
            self.logger.debug("No OTX API key configured; using public search only")

        # Search OTX pulses with relevant keywords
        mentions.extend(self._search_pulses(search_queries, api_key))

        self.logger.info("OTX: found %d relevant mentions", len(mentions))
        return mentions

    def _search_pulses(self, search_queries: list[str], api_key: str) -> list[SourceMention]:
        """Search OTX pulses for PA-relevant threat intelligence."""
        mentions = []
        seen_ids = set()

        # Build targeted search terms
        search_terms = [
            "Pennsylvania ransomware",
            "municipality cyberattack",
            "local government breach",
            "ransomware government",
        ]

        for term in search_terms:
            try:
                headers = {"User-Agent": "pacyberlookup/1.0"}
                if api_key:
                    headers["X-OTX-API-KEY"] = api_key

                params = {"q": term, "limit": 20, "sort": "-created"}
                self.logger.info("Searching OTX pulses: %s", term)

                resp = requests.get(
                    self.OTX_SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                for pulse in results:
                    pulse_id = pulse.get("id", "")
                    if pulse_id in seen_ids:
                        continue
                    seen_ids.add(pulse_id)

                    name = pulse.get("name", "")
                    description = pulse.get("description", "")
                    created = pulse.get("created", "")
                    tags = pulse.get("tags", [])
                    author = pulse.get("author_name", "")
                    indicator_count = len(pulse.get("indicators", []))

                    published = None
                    if created:
                        try:
                            published = dateutil_parser.parse(created)
                            if published.tzinfo is None:
                                published = published.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                    tags_str = ", ".join(tags[:10]) if tags else ""
                    headline = f"OTX Pulse: {name}"
                    raw_text = (
                        f"{name}. {description}. "
                        f"Tags: {tags_str}. "
                        f"Indicators: {indicator_count}. Author: {author}"
                    )

                    mentions.append(SourceMention(
                        headline=headline,
                        source="AlienVault OTX",
                        source_type="threat_intel",
                        url=f"https://otx.alienvault.com/pulse/{pulse_id}",
                        raw_text=raw_text[:2000],
                        published_at=published,
                        source_credibility="national_news",
                    ))
            except Exception:
                self.logger.exception("Error searching OTX for: %s", term)

        return mentions
