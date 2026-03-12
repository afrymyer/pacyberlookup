"""Social media monitoring (Tier 3) - Reddit, RSS-based social feeds.

Treats social mentions as signals only, not confirmation.
"""

import requests
from dateutil import parser as dateutil_parser
from datetime import datetime, timezone

from .base import BaseSource, SourceMention


class RedditSource(BaseSource):
    """Monitor Reddit for PA cyber incident chatter.

    Uses Reddit's public JSON API (no auth required for public subreddit search).
    """

    REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"

    @property
    def source_name(self) -> str:
        return "Reddit"

    @property
    def source_type(self) -> str:
        return "social"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        seen_urls = set()

        for query in search_queries:
            try:
                self.logger.info("Searching Reddit: %s", query)
                params = {
                    "q": query,
                    "sort": "new",
                    "limit": 25,
                    "t": "week",
                }
                resp = requests.get(
                    self.REDDIT_SEARCH_URL,
                    params=params,
                    timeout=30,
                    headers={"User-Agent": "pacyberlookup/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()

                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    pdata = post.get("data", {})
                    url = pdata.get("url", "")
                    permalink = f"https://www.reddit.com{pdata.get('permalink', '')}"

                    if permalink in seen_urls:
                        continue
                    seen_urls.add(permalink)

                    title = pdata.get("title", "")
                    selftext = pdata.get("selftext", "")[:500]
                    subreddit = pdata.get("subreddit", "")
                    created_utc = pdata.get("created_utc")

                    published = None
                    if created_utc:
                        try:
                            published = datetime.fromtimestamp(
                                created_utc, tz=timezone.utc
                            )
                        except (ValueError, TypeError, OSError):
                            pass

                    mentions.append(SourceMention(
                        headline=title,
                        source=f"Reddit r/{subreddit}",
                        source_type="social",
                        url=permalink,
                        raw_text=f"{title} {selftext}",
                        published_at=published,
                        source_credibility="social_mention",
                    ))
            except Exception:
                self.logger.exception("Error searching Reddit for: %s", query)

        self.logger.info("Reddit: found %d mentions across %d queries",
                         len(mentions), len(search_queries))
        return mentions
