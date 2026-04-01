# PA Cyber Incident Detection Feed

Continuously monitors public sources for signs of breaches, ransomware events, cyberattacks, outages, and data incidents tied to Pennsylvania organizations. Scores each item by confidence and routes alerts to Teams, email, SharePoint, or Power BI.

## Architecture

### Source Stack (Layered Model)

| Tier | Sources | Purpose |
|------|---------|---------|
| **Tier 1** | Google News RSS, BleepingComputer, SecurityWeek, DataBreaches.net, Recorded Future, CISA alerts/KEV, HIBP, PA Attorney General | High-confidence public sources |
| **Tier 2** | GDELT event/news monitoring, Ransomware.live leak site monitor | Broad discovery, "first mention" detection |
| **Tier 3** | AlienVault OTX, Shadowserver Foundation | Threat intelligence / enrichment |
| **Tier 4** | Reddit (social/chatter) | Signals only, not confirmation |

### Pipeline

```
Entity List → Search Queries → Source Ingestion → Entity Matching →
Confidence Scoring → Deduplication → AI Summarization → Alert Routing
```

### Confidence Scoring (0–100)

| Component | Points |
|-----------|--------|
| Source credibility (govt: +35, local news: +25, national: +20, social: +5) | 5–35 |
| Entity match (exact: +25, alias: +15, geography-only: +5) | 0–25 |
| Incident language (confirmed: +25, probable: +15, unconfirmed: +5) | 0–25 |
| Cross-source validation (2+: +15, 3+: +25) | 0–25 |

**Bands:** High (75–100) · Medium (50–74) · Low (25–49) · Noise (<25)

### Output Categories

1. **Confirmed Incident** — Public reporting clearly indicates a breach/attack
2. **Suspected Incident** — Credible reporting, no direct confirmation yet
3. **Official Advisory / Risk Context** — CISA alert relevant to PA orgs
4. **Social Chatter / Needs Verification** — Hold until corroborated

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Teams webhook, email settings, etc.

# Initialize database
python -m pacyberlookup init-db

# Seed PA entity reference table
python -m pacyberlookup seed

# Run a single detection cycle
python -m pacyberlookup run

# Start the scheduled feed loop (per-source polling intervals)
python -m pacyberlookup start

# View the CLI status dashboard
python -m pacyberlookup status
python -m pacyberlookup status --hours 48

# Send a digest report now (Teams + email)
python -m pacyberlookup digest
python -m pacyberlookup digest --hours 12

# Check source health (failures, empty results)
python -m pacyberlookup health

# View an incident's timeline (state transitions)
python -m pacyberlookup timeline 42

# Export data for Power BI
python -m pacyberlookup export
```

## Project Structure

```
pacyberlookup/
├── __main__.py          # CLI entry point (run, start, status, digest, health, timeline)
├── models.py            # SQLAlchemy data models
├── orchestrator.py      # Main pipeline coordinator (13 sources, health tracking)
├── scheduler.py         # Per-source polling intervals + digest scheduling
├── search.py            # Search query builder
├── seed.py              # Entity seeding from CSV
├── dashboard.py         # CLI status dashboard
├── geo.py               # County-level geo enrichment (67 PA counties)
├── timeline.py          # Incident lifecycle state machine
├── health.py            # Source health monitoring + failure detection
├── sources/
│   ├── base.py          # Base source class (retry, rate limiting)
│   ├── news.py          # Google News RSS
│   ├── gdelt.py         # GDELT API
│   ├── cisa.py          # CISA alerts + KEV catalog
│   ├── cybernews.py     # BleepingComputer, SecurityWeek, DataBreaches.net, Recorded Future
│   ├── hibp.py          # Have I Been Pwned breach monitoring
│   ├── otx.py           # AlienVault OTX threat intelligence
│   ├── ransomware_live.py  # Ransomware leak site monitoring
│   ├── shadowserver.py  # Shadowserver Foundation reports
│   ├── pa_attorney_general.py  # PA AG breach notification scraper
│   └── social.py        # Reddit
├── scoring/
│   ├── confidence.py    # Confidence scoring model
│   ├── dedup.py         # Deduplication logic
│   └── summarizer.py    # AI / template summarization
├── alerts/
│   ├── teams.py         # Teams webhook Adaptive Cards
│   ├── email.py         # Email digest
│   ├── sharepoint.py    # SharePoint list push
│   ├── digest.py        # Daily digest reports (Teams + email)
│   └── watchlist.py     # Client/prospect watchlist with talking points
├── export/
│   └── powerbi.py       # CSV/JSON export for Power BI
└── utils/
    ├── config.py        # YAML + env config loader
    └── text.py          # Text normalization & matching
```

## Entity Reference Table

Seed data in `seed_data/pa_entities.csv` includes ~90 PA organizations across:
- Municipalities (townships, boroughs, cities)
- Counties
- School districts
- Healthcare systems
- Utilities
- Municipal authorities
- Nonprofits
- State agencies

Each entity supports multiple aliases for matching inconsistent local reporting.

## Configuration

- `config/settings.yaml` — Polling intervals, scoring weights, keyword lists
- `.env` — API keys, webhook URLs, database URL, feature flags

## Testing

```bash
python -m pytest tests/ -v
```

## Power BI Integration

Export commands generate:
- `exports/dim_entities_pa.csv` — Entity dimension table
- `exports/fact_incidents_scored.csv` — Scored incidents fact table
- `exports/fact_incidents_scored.json` — JSON format for streaming datasets

Recommended dashboard views:
- Incident count by county / entity type
- Confirmed vs suspected over time
- Top affected sectors
- Client/prospect proximity overlay
