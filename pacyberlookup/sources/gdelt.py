"""GDELT event and news monitoring for 'first mention' detection."""

from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class GDELTSource(BaseSource):
    """Fetch articles from GDELT DOC API (updated every 15 minutes)."""

    GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

    @property
    def source_name(self) -> str:
        return "GDELT"

    @property
    def source_type(self) -> str:
        return "gdelt"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        seen_urls = set()

        for query in search_queries:
            try:
                params = {
                    "query": query,
                    "mode": "ArtList",
                    "maxrecords": 50,
                    "format": "json",
                    "sort": "DateDesc",
                    "timespan": "7d",
                }
                self.logger.info("Fetching GDELT: %s", query)
                resp = requests.get(
                    self.GDELT_DOC_API,
                    params=params,
                    timeout=30,
                    headers={"User-Agent": "pacyberlookup/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()

                articles = data.get("articles", [])
                for article in articles:
                    url = article.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    published = None
                    seendate = article.get("seendate", "")
                    if seendate:
                        try:
                            # GDELT format: YYYYMMDDTHHMMSSZ
                            published = datetime.strptime(
                                seendate.replace("Z", ""), "%Y%m%dT%H%M%S"
                            ).replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                    title = article.get("title", "")
                    domain = article.get("domain", "")
                    source_country = article.get("sourcecountry", "")

                    mentions.append(SourceMention(
                        headline=title,
                        source=domain or "GDELT",
                        source_type="gdelt",
                        url=url,
                        raw_text=title,
                        published_at=published,
                        # GDELT articles are generally news sources
                        source_credibility="local_regional_news",
                    ))
            except Exception:
                self.logger.exception("Error fetching GDELT for query: %s", query)

        self.logger.info("GDELT: found %d mentions across %d queries",
                         len(mentions), len(search_queries))
        return mentions
