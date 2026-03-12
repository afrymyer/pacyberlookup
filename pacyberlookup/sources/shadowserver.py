"""Shadowserver Foundation — internet exposure alerts.

Shadowserver collects global internet telemetry and provides reports about:
- Exposed systems
- Vulnerable infrastructure
- Botnet activity

Large organizations and municipalities sometimes show up in exposure reports.

Note: Shadowserver reports are typically delivered via email subscription or API
for organizations that register. The public API provides some aggregate data.
"""

import os
from datetime import datetime, timezone

import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class ShadowserverSource(BaseSource):
    """Shadowserver exposure and vulnerability monitoring.

    Uses the Shadowserver public API to check for exposed infrastructure
    and the reports API (if configured) for detailed exposure data.
    """

    # Shadowserver public stats/reports APIs
    SHADOWSERVER_STATS_URL = "https://api.shadowserver.org/reports/stats"
    SHADOWSERVER_QUERY_URL = "https://api.shadowserver.org/reports/query"

    @property
    def source_name(self) -> str:
        return "Shadowserver"

    @property
    def source_type(self) -> str:
        return "threat_intel"

    def _get_api_key(self) -> str:
        return os.getenv("SHADOWSERVER_API_KEY", "")

    def _get_api_secret(self) -> str:
        return os.getenv("SHADOWSERVER_API_SECRET", "")

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        """Fetch Shadowserver exposure data.

        If API credentials are configured, queries the reports API for
        PA-specific exposure data. Otherwise, attempts public endpoint queries.
        """
        mentions = []

        api_key = self._get_api_key()
        api_secret = self._get_api_secret()

        if api_key and api_secret:
            mentions.extend(self._fetch_reports(api_key, api_secret, search_queries))
        else:
            self.logger.info(
                "No Shadowserver API credentials configured; "
                "skipping detailed reports (configure SHADOWSERVER_API_KEY "
                "and SHADOWSERVER_API_SECRET for full access)"
            )

        # Also check the public scan data for PA-related exposures
        mentions.extend(self._fetch_public_stats(search_queries))

        self.logger.info("Shadowserver: found %d relevant mentions", len(mentions))
        return mentions

    def _fetch_reports(
        self, api_key: str, api_secret: str, search_queries: list[str]
    ) -> list[SourceMention]:
        """Query Shadowserver reports API for exposure data."""
        mentions = []
        try:
            self.logger.info("Querying Shadowserver reports API")

            # Query for PA-specific exposure reports
            report_types = [
                "scan_ssl",       # Exposed SSL/TLS services
                "scan_rdp",       # Exposed RDP
                "scan_smb",       # Exposed SMB
                "scan_http",      # Exposed HTTP services
            ]

            for report_type in report_types:
                try:
                    payload = {
                        "apikey": api_key,
                        "secret": api_secret,
                        "type": report_type,
                        "query": {"geo": "US", "region": "Pennsylvania"},
                        "limit": 50,
                    }
                    resp = requests.post(
                        self.SHADOWSERVER_QUERY_URL,
                        json=payload,
                        timeout=30,
                        headers={"User-Agent": "pacyberlookup/1.0"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list):
                            for record in data:
                                ip = record.get("ip", "")
                                hostname = record.get("hostname", "")
                                asn_name = record.get("asn_name", "")
                                port = record.get("port", "")
                                tag = record.get("tag", report_type)
                                timestamp = record.get("timestamp", "")

                                published = None
                                if timestamp:
                                    try:
                                        published = dateutil_parser.parse(timestamp)
                                        if published.tzinfo is None:
                                            published = published.replace(tzinfo=timezone.utc)
                                    except (ValueError, TypeError):
                                        pass

                                headline = (
                                    f"Shadowserver: Exposed {tag} service "
                                    f"at {hostname or ip}:{port}"
                                )
                                raw_text = (
                                    f"Exposed {tag} service detected. "
                                    f"IP: {ip}, Hostname: {hostname}, "
                                    f"Port: {port}, ASN: {asn_name}"
                                )

                                mentions.append(SourceMention(
                                    headline=headline,
                                    source="Shadowserver",
                                    source_type="threat_intel",
                                    url="https://www.shadowserver.org/what-we-do/network-reporting/",
                                    raw_text=raw_text,
                                    published_at=published,
                                    source_credibility="government_advisory",
                                ))
                except Exception:
                    self.logger.exception("Error querying Shadowserver for %s", report_type)

        except Exception:
            self.logger.exception("Error accessing Shadowserver reports API")

        return mentions

    def _fetch_public_stats(self, search_queries: list[str]) -> list[SourceMention]:
        """Check Shadowserver public statistics for PA-relevant data."""
        mentions = []
        try:
            # The public stats endpoint provides aggregate scan statistics
            # We check for notable spikes in PA-region exposure
            self.logger.info("Checking Shadowserver public stats")

            params = {
                "geo": "US",
                "query": "scan",
                "limit": 10,
            }
            resp = requests.get(
                self.SHADOWSERVER_STATS_URL,
                params=params,
                timeout=15,
                headers={"User-Agent": "pacyberlookup/1.0"},
            )

            if resp.status_code == 200:
                data = resp.json()
                # Public stats are aggregate; useful for context but not
                # individual victim identification
                if isinstance(data, dict) and data:
                    for scan_type, count in data.items():
                        if isinstance(count, (int, float)) and count > 0:
                            mentions.append(SourceMention(
                                headline=f"Shadowserver: {count} exposed {scan_type} services in US",
                                source="Shadowserver",
                                source_type="threat_intel",
                                url="https://www.shadowserver.org/what-we-do/network-reporting/",
                                raw_text=f"Shadowserver reports {count} exposed {scan_type} services in US region",
                                source_credibility="government_advisory",
                            ))
        except Exception:
            self.logger.debug("Shadowserver public stats unavailable (expected without credentials)")

        return mentions
