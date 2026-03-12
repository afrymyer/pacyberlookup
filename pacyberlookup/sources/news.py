"""Google News RSS ingestion for PA cyber incident monitoring."""

import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import atoma
import requests
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention

# Known PA local/regional news domains for credibility scoring
PA_LOCAL_NEWS_DOMAINS = {
    "pennlive.com", "inquirer.com", "post-gazette.com", "mcall.com",
    "dailylocal.com", "timesleader.com", "citizensvoice.com",
    "pottsmerc.com", "delcotimes.com", "thereporteronline.com",
    "lancasteronline.com", "ydr.com", "goerie.com", "standardspeaker.com",
    "thetimes-tribune.com", "dailyitem.com", "sungazette.com",
    "observer-reporter.com", "butlereagle.com", "triblive.com",
    "wtae.com", "kdka.com", "wpxi.com", "6abc.com", "fox29.com",
    "pahomepage.com", "abc27.com", "wgal.com", "wnep.com",
    "witf.org", "whyy.org", "wesa.fm",
}

NATIONAL_NEWS_DOMAINS = {
    "cnn.com", "nytimes.com", "washingtonpost.com", "reuters.com",
    "apnews.com", "bbc.com", "nbcnews.com", "cbsnews.com",
    "foxnews.com", "abcnews.go.com", "usatoday.com", "thehill.com",
    "politico.com", "axios.com", "bleepingcomputer.com", "therecord.media",
    "darkreading.com", "krebsonsecurity.com", "cyberscoop.com",
    "securityweek.com", "threatpost.com",
}


def _classify_source(url: str) -> str:
    """Classify a URL as local_regional_news, national_news, or unknown."""
    if not url:
        return "unknown"
    url_lower = url.lower()
    for domain in PA_LOCAL_NEWS_DOMAINS:
        if domain in url_lower:
            return "local_regional_news"
    for domain in NATIONAL_NEWS_DOMAINS:
        if domain in url_lower:
            return "national_news"
    return "local_regional_news"  # default assumption for news results


def _clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


class GoogleNewsSource(BaseSource):
    """Fetch results from Google News RSS feeds."""

    GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    @property
    def source_name(self) -> str:
        return "Google News"

    @property
    def source_type(self) -> str:
        return "news"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        seen_urls = set()

        for query in search_queries:
            try:
                url = self.GOOGLE_NEWS_RSS_URL.format(query=quote_plus(query))
                self.logger.info("Fetching Google News RSS: %s", query)
                resp = requests.get(url, timeout=30, headers={
                    "User-Agent": "pacyberlookup/1.0 (+https://github.com/pacyberlookup)"
                })
                resp.raise_for_status()

                feed = atoma.parse_rss_bytes(resp.content)
                for item in feed.items:
                    link = item.link or ""
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)

                    published = None
                    if item.pub_date:
                        published = item.pub_date
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)

                    headline = _clean_html(item.title or "")
                    description = _clean_html(item.description or "")
                    source_name = item.source or "Google News"

                    mentions.append(SourceMention(
                        headline=headline,
                        source=source_name,
                        source_type="news",
                        url=link,
                        raw_text=f"{headline} {description}",
                        published_at=published,
                        source_credibility=_classify_source(link),
                    ))
            except Exception:
                self.logger.exception("Error fetching Google News for query: %s", query)

        self.logger.info("Google News: found %d mentions across %d queries",
                         len(mentions), len(search_queries))
        return mentions
