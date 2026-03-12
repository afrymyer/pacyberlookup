"""Pennsylvania Attorney General BPINA breach notice scraper.

The PA Attorney General's Bureau of Consumer Protection publishes
breach notifications. This is the most authoritative PA-specific
source for confirmed data breaches.

Source: https://www.attorneygeneral.gov/taking-action/data-breach-notifications/
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from .base import BaseSource, SourceMention


class PAAttorneyGeneralSource(BaseSource):
    """Scrape PA Attorney General breach notification page.

    Polls the AG's data breach notification page for new entries
    and matches them against PA entity keywords.
    """

    AG_BREACH_URL = "https://www.attorneygeneral.gov/taking-action/data-breach-notifications/"

    @property
    def source_name(self) -> str:
        return "PA Attorney General"

    @property
    def source_type(self) -> str:
        return "government"

    def fetch(self, search_queries: list[str]) -> list[SourceMention]:
        mentions = []
        try:
            self.logger.info("Fetching PA Attorney General breach notifications")
            resp = requests.get(
                self.AG_BREACH_URL,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; pacyberlookup/1.0; "
                        "cybersecurity monitoring)"
                    ),
                },
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Build keyword set for entity matching
            keywords = set()
            for q in search_queries:
                for word in q.lower().replace('"', '').split():
                    if len(word) > 3:
                        keywords.add(word)
            keywords.update([
                "pennsylvania", "township", "borough", "municipality",
                "county", "authority", "school", "hospital", "health",
                "water", "sewer", "utility",
            ])

            # Parse breach notification entries
            # The AG page typically lists breaches in structured HTML
            # Look for common patterns: tables, lists, article blocks
            entries = self._parse_entries(soup)

            for entry in entries:
                title = entry.get("title", "")
                date_str = entry.get("date", "")
                description = entry.get("description", "")
                link = entry.get("link", self.AG_BREACH_URL)

                combined = f"{title} {description}".lower()

                # Check relevance
                if not any(kw in combined for kw in keywords):
                    continue

                published = None
                if date_str:
                    try:
                        published = dateutil_parser.parse(date_str)
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                headline = f"PA AG Breach Notice: {title}" if title else "PA AG Breach Notification"

                mentions.append(SourceMention(
                    headline=headline,
                    source="PA Attorney General",
                    source_type="government",
                    url=link,
                    raw_text=f"{headline}. {description}",
                    published_at=published,
                    source_credibility="government_advisory",
                ))

        except Exception:
            self.logger.exception("Error fetching PA Attorney General breach page")

        self.logger.info("PA Attorney General: found %d relevant mentions", len(mentions))
        return mentions

    def _parse_entries(self, soup: BeautifulSoup) -> list[dict]:
        """Extract breach notification entries from the AG page HTML.

        Tries multiple parsing strategies since the page structure may vary.
        """
        entries = []

        # Strategy 1: Look for article/post elements
        for article in soup.find_all(["article", "div"], class_=re.compile(
            r"(post|entry|breach|notification|item|card)", re.I
        )):
            entry = self._extract_entry_from_element(article)
            if entry.get("title"):
                entries.append(entry)

        # Strategy 2: Look for table rows
        if not entries:
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                for row in rows[1:]:  # skip header
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        title = cells[0].get_text(strip=True)
                        date_str = ""
                        description = ""
                        link = self.AG_BREACH_URL

                        # Look for a link in the first cell
                        a_tag = cells[0].find("a")
                        if a_tag and a_tag.get("href"):
                            href = a_tag["href"]
                            if not href.startswith("http"):
                                href = f"https://www.attorneygeneral.gov{href}"
                            link = href

                        if len(cells) >= 2:
                            date_str = cells[1].get_text(strip=True)
                        if len(cells) >= 3:
                            description = cells[2].get_text(strip=True)

                        if title:
                            entries.append({
                                "title": title,
                                "date": date_str,
                                "description": description,
                                "link": link,
                            })

        # Strategy 3: Look for list items with links
        if not entries:
            for li in soup.find_all("li"):
                a_tag = li.find("a")
                if a_tag:
                    text = li.get_text(strip=True)
                    # Look for breach-related keywords
                    if any(kw in text.lower() for kw in ["breach", "notification", "data"]):
                        href = a_tag.get("href", "")
                        if not href.startswith("http"):
                            href = f"https://www.attorneygeneral.gov{href}"
                        entries.append({
                            "title": a_tag.get_text(strip=True),
                            "date": "",
                            "description": text,
                            "link": href,
                        })

        # Strategy 4: Look for heading + paragraph pairs
        if not entries:
            for heading in soup.find_all(["h2", "h3", "h4"]):
                text = heading.get_text(strip=True)
                if any(kw in text.lower() for kw in [
                    "breach", "notification", "data", "incident",
                    "security", "unauthorized",
                ]):
                    desc = ""
                    next_el = heading.find_next_sibling(["p", "div"])
                    if next_el:
                        desc = next_el.get_text(strip=True)

                    a_tag = heading.find("a")
                    link = self.AG_BREACH_URL
                    if a_tag and a_tag.get("href"):
                        href = a_tag["href"]
                        if not href.startswith("http"):
                            href = f"https://www.attorneygeneral.gov{href}"
                        link = href

                    entries.append({
                        "title": text,
                        "date": "",
                        "description": desc,
                        "link": link,
                    })

        return entries

    def _extract_entry_from_element(self, element) -> dict:
        """Extract title, date, description, link from an HTML element."""
        title = ""
        date_str = ""
        description = ""
        link = self.AG_BREACH_URL

        # Title from heading or first strong/bold element
        heading = element.find(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
        if heading:
            title = heading.get_text(strip=True)

        # Link
        a_tag = element.find("a")
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            if not href.startswith("http"):
                href = f"https://www.attorneygeneral.gov{href}"
            link = href
            if not title:
                title = a_tag.get_text(strip=True)

        # Date - look for time element or date-like text
        time_el = element.find("time")
        if time_el:
            date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
        else:
            # Try to find date pattern in text
            text = element.get_text()
            date_match = re.search(
                r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})", text
            )
            if date_match:
                date_str = date_match.group(1)

        # Description
        p_tag = element.find("p")
        if p_tag:
            description = p_tag.get_text(strip=True)
        elif not description:
            description = element.get_text(strip=True)[:500]

        return {
            "title": title,
            "date": date_str,
            "description": description,
            "link": link,
        }
