# PA Cyber Incident Detection Feed

Continuously monitors public sources for signs of breaches, ransomware events, cyberattacks, outages, and data incidents tied to Pennsylvania organizations. Scores each item by confidence and routes alerts to Teams, email, SharePoint, or Power BI.

## Architecture

### Source Stack (Layered Model)

| Tier | Sources | Purpose |
|------|---------|---------|
| **Tier 1** | Google News RSS, CISA alerts/advisories, PA Attorney General context | High-confidence public sources |
| **Tier 2** | GDELT event/news monitoring | Broad discovery, "first mention" detection |
| **Tier 3** | Reddit (social/chatter) | Signals only, not confirmation |

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

# Start the scheduled feed loop
python -m pacyberlookup start

# Export data for Power BI
python -m pacyberlookup export
```

## Project Structure

```
pacyberlookup/
├── __main__.py          # CLI entry point
├── models.py            # SQLAlchemy data models
├── orchestrator.py      # Main pipeline coordinator
├── scheduler.py         # Scheduled loop runner
├── search.py            # Search query builder
├── seed.py              # Entity seeding from CSV
├── sources/
│   ├── base.py          # Base source class
│   ├── news.py          # Google News RSS
│   ├── gdelt.py         # GDELT API
│   ├── cisa.py          # CISA alerts + KEV
│   └── social.py        # Reddit
├── scoring/
│   ├── confidence.py    # Confidence scoring model
│   ├── dedup.py         # Deduplication logic
│   └── summarizer.py    # AI / template summarization
├── alerts/
│   ├── teams.py         # Teams webhook cards
│   ├── email.py         # Email digest
│   └── sharepoint.py    # SharePoint list push
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
