# DC Watcher

Congressional stock trade tracker PWA. Tracks U.S. Congressional stock trades, providing a leaderboard, cluster detection signals, and committee cross-referencing.

**Cost: $0/month**

## Architecture

| Component | Technology |
|-----------|-----------|
| Data pipeline | Python (requests, pdfplumber, BeautifulSoup, yfinance) |
| Automation | GitHub Actions (daily cron) |
| Database | JSON + SQLite files in repo |
| Frontend | React 19 + Vite + TypeScript |
| PWA | vite-plugin-pwa (Workbox) |
| Hosting | Cloudflare Pages |

## Project Structure

```
DC-Watcher/
├── scraper/          # Python data pipeline
├── data/             # Generated data (committed by Actions)
├── web/              # React PWA
└── .github/workflows # Automation
```

## Quick Start

### Run the data pipeline

```bash
cd scraper
pip install -r requirements.txt
python fetch_s3_data.py   # Fetch from S3 datasets
python enrich.py          # Add stock prices, compute stats
python build_db.py        # Build SQLite database
```

### Run the frontend

```bash
cd web
npm install
npm run dev
```

The app runs at `http://localhost:5173` with sample data included in `web/public/data/`.

## Data Sources

- **Primary**: Community-maintained S3 buckets (house-stock-watcher-data, senate-stock-watcher-data)
- **Fallback**: House Clerk disclosures (XML ZIP) and Senate eFD (HTML scraping)
- **Stock Prices**: Yahoo Finance via yfinance

## Deployment

The app deploys to Cloudflare Pages via GitHub Actions when changes are pushed to `main`.

To set up deployment, add these repository secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Then create a Pages project named `dc-watcher` in your Cloudflare dashboard.

## Phases

- **Phase 1 (MVP)**: Trade list, leaderboard, politician detail, search, PWA
- **Phase 2**: Charts (Recharts), cluster detection, stock price overlays
- **Phase 3**: Committee integration, alerts, advanced features
"# dcwatch" 
"# dcwatch" 
