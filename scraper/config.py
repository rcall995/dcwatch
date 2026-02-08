"""
DC-Watcher configuration: constants, paths, and shared mappings.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# S3 data sources (community-maintained, free)
HOUSE_S3_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_S3_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"

# Official sources (fallback)
HOUSE_DISCLOSURE_BASE = "https://disclosures-clerk.house.gov"
SENATE_EFD_BASE = (
    "https://efts.sec.gov/LATEST/search-index"
    "?q=%22periodic+transaction+report%22&dateRange=custom"
)

# Output files
TRADES_RAW_JSON = DATA_DIR / "trades_raw.json"
TRADES_JSON = DATA_DIR / "trades.json"
SUMMARY_JSON = DATA_DIR / "summary.json"
LATEST_JSON = DATA_DIR / "latest.json"
SIGNALS_JSON = DATA_DIR / "signals.json"
DB_PATH = DATA_DIR / "dc-watcher.db"

# Enrichment
PRICE_CACHE_DIR = DATA_DIR / "price_cache"
PRICE_CACHE_DIR.mkdir(exist_ok=True)

# Amount range mapping for House/Senate disclosures
AMOUNT_RANGES: dict[str, tuple[int, int]] = {
    "$1,001 - $15,000": (1001, 15000),
    "$1,001 -": (1001, 15000),
    "$15,001 - $50,000": (15001, 50000),
    "$50,001 - $100,000": (50001, 100000),
    "$100,001 - $250,000": (100001, 250000),
    "$250,001 - $500,000": (250001, 500000),
    "$500,001 - $1,000,000": (500001, 1000000),
    "$1,000,001 - $5,000,000": (1000001, 5000000),
    "$5,000,001 - $25,000,000": (5000001, 25000000),
    "$25,000,001 - $50,000,000": (25000001, 50000000),
    "$50,000,001 +": (50000001, 100000000),
    "Over $50,000,000": (50000001, 100000000),
}

# Request settings
REQUEST_TIMEOUT = 30  # seconds
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
