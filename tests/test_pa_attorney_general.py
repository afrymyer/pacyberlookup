"""Tests for PA Attorney General breach scraper."""

from unittest.mock import MagicMock, patch

from pacyberlookup.sources.pa_attorney_general import PAAttorneyGeneralSource


def _make_source():
    return PAAttorneyGeneralSource(config={})


class TestPAAttorneyGeneralSource:
    def test_source_properties(self):
        source = _make_source()
        assert source.source_name == "PA Attorney General"
        assert source.source_type == "government"

    def test_parse_entries_article_strategy(self):
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <div class="post">
            <h3><a href="/breach/1">Acme Township Data Breach</a></h3>
            <time datetime="2025-01-15">January 15, 2025</time>
            <p>Acme Township experienced a data breach affecting 5000 residents.</p>
        </div>
        <div class="entry">
            <h3>Hospital System Notification</h3>
            <p>A hospital system reported unauthorized access.</p>
        </div>
        </body></html>
        """
        source = _make_source()
        soup = BeautifulSoup(html, "html.parser")
        entries = source._parse_entries(soup)
        assert len(entries) >= 1
        assert "Acme Township" in entries[0]["title"]

    def test_parse_entries_table_strategy(self):
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <table>
            <tr><th>Entity</th><th>Date</th><th>Details</th></tr>
            <tr>
                <td><a href="/breach/100">Springfield Township</a></td>
                <td>2025-02-01</td>
                <td>Ransomware incident affecting municipality systems</td>
            </tr>
        </table>
        </body></html>
        """
        source = _make_source()
        soup = BeautifulSoup(html, "html.parser")
        entries = source._parse_entries(soup)
        assert len(entries) >= 1
        assert "Springfield Township" in entries[0]["title"]

    def test_parse_entries_list_strategy(self):
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <ul>
            <li><a href="/breach/200">Data breach notification - County Hospital</a></li>
            <li><a href="/other">Unrelated link</a></li>
        </ul>
        </body></html>
        """
        source = _make_source()
        soup = BeautifulSoup(html, "html.parser")
        entries = source._parse_entries(soup)
        assert len(entries) >= 1

    def test_parse_entries_heading_strategy(self):
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <h2>Data Breach Notification: School District</h2>
        <p>The school district notified residents of unauthorized access to student records.</p>
        </body></html>
        """
        source = _make_source()
        soup = BeautifulSoup(html, "html.parser")
        entries = source._parse_entries(soup)
        assert len(entries) >= 1
        assert "Breach" in entries[0]["title"] or "breach" in entries[0]["title"].lower()

    @patch("pacyberlookup.sources.pa_attorney_general.requests.get")
    def test_fetch_with_keyword_match(self, mock_get):
        html = """
        <html><body>
        <div class="breach-notification">
            <h3>Township Water Authority Security Incident</h3>
            <p>A Pennsylvania township water authority reported a cybersecurity incident.</p>
        </div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = _make_source()
        mentions = source.fetch(['"township water authority"', "pennsylvania breach"])
        # Should match on keyword "township" / "authority" / "pennsylvania"
        assert len(mentions) >= 1
        assert mentions[0].source_type == "government"
        assert mentions[0].source_credibility == "government_advisory"

    @patch("pacyberlookup.sources.pa_attorney_general.requests.get")
    def test_fetch_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        source = _make_source()
        mentions = source.fetch(["test query"])
        assert mentions == []
