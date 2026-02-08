"""
DC-Watcher: Primary data fetcher.

Pulls congressional stock trade disclosures from the community-maintained
S3 buckets (house-stock-watcher-data and senate-stock-watcher-data),
normalizes both feeds into a unified schema, deduplicates, and writes
the result to data/trades_raw.json and data/trades.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from datetime import date, datetime
from typing import Any

import requests

from config import (
    AMOUNT_RANGES,
    HOUSE_S3_URL,
    REQUEST_TIMEOUT,
    SENATE_S3_URL,
    TRADES_JSON,
    TRADES_RAW_JSON,
    USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("fetch_s3_data")

# ---------------------------------------------------------------------------
# Known party affiliations for House members.
# The House S3 data does NOT include party, so we maintain a lookup.
# This covers the most prominent traders; unknown members default to "".
# ---------------------------------------------------------------------------
PARTY_MAP: dict[str, str] = {
    # Democrats
    "Nancy Pelosi": "D",
    "Ro Khanna": "D",
    "Josh Gottheimer": "D",
    "Suzan DelBene": "D",
    "Debbie Wasserman Schultz": "D",
    "Raja Krishnamoorthi": "D",
    "Lois Frankel": "D",
    "Marie Newman": "D",
    "Tom Malinowski": "D",
    "Susie Lee": "D",
    "Kathy Manning": "D",
    "Alan Lowenthal": "D",
    "Earl Blumenauer": "D",
    "Bobby Scott": "D",
    "Ed Perlmutter": "D",
    "Gilbert Cisneros": "D",
    # Republicans
    "Dan Crenshaw": "R",
    "Michael McCaul": "R",
    "Pat Fallon": "R",
    "John Curtis": "R",
    "Kevin Hern": "R",
    "Steve Scalise": "R",
    "Marjorie Taylor Greene": "R",
    "Mark Green": "R",
    "French Hill": "R",
    "Brian Mast": "R",
    "Gary Palmer": "R",
    "Austin Scott": "R",
    "Mike Kelly": "R",
    "John Rutherford": "R",
    "Greg Steube": "R",
    "Diana Harshbarger": "R",
    "Tommy Tuberville": "R",
    "Virginia Foxx": "R",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(
    politician: str,
    tx_date: str,
    ticker: str,
    tx_type: str,
    amount_low: int,
    amount_high: int,
) -> str:
    """Deterministic trade ID from the key fields."""
    raw = f"{politician}|{tx_date}|{ticker}|{tx_type}|{amount_low}|{amount_high}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _parse_date(raw: str | None) -> str:
    """Parse various date formats into YYYY-MM-DD, or return empty string."""
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _parse_amount(raw: str | None) -> tuple[int, int]:
    """Map an amount-range string to (low, high) integers."""
    if not raw:
        return (0, 0)
    raw = raw.strip()
    # Direct lookup
    if raw in AMOUNT_RANGES:
        return AMOUNT_RANGES[raw]
    # Fuzzy match: strip whitespace variations and try again
    normalised = re.sub(r"\s+", " ", raw).strip()
    for key, val in AMOUNT_RANGES.items():
        if normalised.startswith(key.split(" -")[0]) or key.startswith(normalised.split(" -")[0]):
            return val
    # Try to pull numbers directly (e.g. "$1,001 - $15,000")
    nums = re.findall(r"[\d,]+", raw)
    if len(nums) >= 2:
        try:
            return (int(nums[0].replace(",", "")), int(nums[1].replace(",", "")))
        except ValueError:
            pass
    if len(nums) == 1:
        try:
            v = int(nums[0].replace(",", ""))
            return (v, v)
        except ValueError:
            pass
    return (0, 0)


def _normalise_tx_type(raw: str | None) -> str:
    """Normalise transaction type string."""
    if not raw:
        return "purchase"
    t = raw.strip().lower()
    if "sale" in t and "full" in t:
        return "sale_full"
    if "sale" in t and "partial" in t:
        return "sale_partial"
    if "sale" in t:
        return "sale_partial"  # default sale -> partial
    if "exchange" in t:
        return "exchange"
    return "purchase"


def _detect_asset_type(description: str | None) -> str:
    """Guess asset type from the asset description string."""
    if not description:
        return "stock"
    d = description.lower()
    if any(kw in d for kw in ("option", "call", "put")):
        return "option"
    if any(kw in d for kw in ("etf", "exchange traded", "exchange-traded", "spdr", "ishares", "vanguard")):
        return "etf"
    if any(kw in d for kw in ("bond", "treasury", "note", "municipal", "t-bill")):
        return "bond"
    if any(kw in d for kw in ("crypto", "bitcoin", "ethereum")):
        return "other"
    return "stock"


def _normalise_owner(raw: str | None) -> str:
    """Normalise the owner field."""
    if not raw:
        return "self"
    o = raw.strip().lower()
    if "spouse" in o:
        return "spouse"
    if "joint" in o:
        return "joint"
    if "dependent" in o or "child" in o:
        return "dependent"
    return "self"


def _days_late(tx_date_str: str, disclosure_date_str: str) -> int:
    """
    Compute how many days late a filing was.
    STOCK Act requires disclosure within 45 days of the transaction.
    Returns 0 if on-time or if dates are missing.
    """
    if not tx_date_str or not disclosure_date_str:
        return 0
    try:
        tx_dt = date.fromisoformat(tx_date_str)
        disc_dt = date.fromisoformat(disclosure_date_str)
        delta = (disc_dt - tx_dt).days - 45
        return max(0, delta)
    except (ValueError, TypeError):
        return 0


def _state_from_district(district: str | None) -> str:
    """Extract state abbreviation from a House district string like 'CA05'."""
    if not district:
        return ""
    m = re.match(r"([A-Z]{2})", district.upper())
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# House S3 normalisation
# ---------------------------------------------------------------------------

def _normalise_house_trade(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a single House S3 record into the unified schema."""
    politician = (raw.get("representative") or "").strip()
    if not politician:
        return None

    ticker = (raw.get("ticker") or "").strip().upper()
    if ticker in ("N/A", "--", ""):
        ticker = ""

    tx_date = _parse_date(raw.get("transaction_date"))
    disclosure_date = _parse_date(raw.get("disclosure_date"))
    tx_type = _normalise_tx_type(raw.get("type"))
    amount_low, amount_high = _parse_amount(raw.get("amount"))
    asset_desc = (raw.get("asset_description") or "").strip()
    owner = _normalise_owner(raw.get("owner"))
    filing_url = (raw.get("ptr_link") or "").strip()
    district = (raw.get("district") or "").strip()
    state = _state_from_district(district)
    party = PARTY_MAP.get(politician, "")

    trade_id = _make_id(politician, tx_date, ticker, tx_type, amount_low, amount_high)

    return {
        "id": trade_id,
        "politician": politician,
        "party": party,
        "state": state,
        "chamber": "house",
        "ticker": ticker,
        "asset_description": asset_desc,
        "asset_type": _detect_asset_type(asset_desc),
        "tx_type": tx_type,
        "tx_date": tx_date,
        "disclosure_date": disclosure_date,
        "amount_low": amount_low,
        "amount_high": amount_high,
        "owner": owner,
        "filing_url": filing_url,
        "is_amended": False,
        "days_late": _days_late(tx_date, disclosure_date),
    }


# ---------------------------------------------------------------------------
# Senate S3 normalisation
# ---------------------------------------------------------------------------

def _normalise_senate_trade(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a single Senate S3 record into the unified schema."""
    politician = (raw.get("senator") or "").strip()
    if not politician:
        return None

    ticker = (raw.get("ticker") or "").strip().upper()
    if ticker in ("N/A", "--", ""):
        ticker = ""

    tx_date = _parse_date(raw.get("transaction_date"))
    disclosure_date = _parse_date(raw.get("disclosure_date"))
    tx_type = _normalise_tx_type(raw.get("type"))
    amount_low, amount_high = _parse_amount(raw.get("amount"))
    asset_desc = (raw.get("asset_description") or "").strip()
    owner = _normalise_owner(raw.get("owner"))
    filing_url = (raw.get("ptr_link") or "").strip()
    state = (raw.get("office") or "").strip()
    # Senate data sometimes has the full state name; we want 2-letter code
    if len(state) > 2:
        state = _state_abbrev(state)
    party = (raw.get("party") or "").strip()
    # Normalise party to single letter
    if party.lower().startswith("democrat"):
        party = "D"
    elif party.lower().startswith("republican"):
        party = "R"
    elif party.lower().startswith("independent"):
        party = "I"
    elif len(party) > 1:
        party = party[0].upper()

    trade_id = _make_id(politician, tx_date, ticker, tx_type, amount_low, amount_high)

    return {
        "id": trade_id,
        "politician": politician,
        "party": party,
        "state": state,
        "chamber": "senate",
        "ticker": ticker,
        "asset_description": asset_desc,
        "asset_type": _detect_asset_type(asset_desc),
        "tx_type": tx_type,
        "tx_date": tx_date,
        "disclosure_date": disclosure_date,
        "amount_low": amount_low,
        "amount_high": amount_high,
        "owner": owner,
        "filing_url": filing_url,
        "is_amended": False,
        "days_late": _days_late(tx_date, disclosure_date),
    }


# State name to abbreviation helper
_STATE_ABBREVS: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def _state_abbrev(name: str) -> str:
    """Convert a full state name to its 2-letter abbreviation."""
    return _STATE_ABBREVS.get(name.strip().lower(), name.strip()[:2].upper())


# ---------------------------------------------------------------------------
# Fetch and combine
# ---------------------------------------------------------------------------

def fetch_house_s3() -> list[dict[str, Any]]:
    """Fetch and normalise all House trades from the S3 bucket."""
    log.info("Fetching House trades from S3: %s", HOUSE_S3_URL)
    try:
        resp = requests.get(
            HOUSE_S3_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        raw_data = resp.json()
    except requests.RequestException as exc:
        log.error("Failed to fetch House S3 data: %s", exc)
        return []

    if not isinstance(raw_data, list):
        log.warning("House S3 response is not a list; got %s", type(raw_data).__name__)
        return []

    trades: list[dict[str, Any]] = []
    for record in raw_data:
        normalised = _normalise_house_trade(record)
        if normalised is not None:
            trades.append(normalised)

    log.info("Normalised %d House trades from %d raw records", len(trades), len(raw_data))
    return trades


def fetch_senate_s3() -> list[dict[str, Any]]:
    """Fetch and normalise all Senate trades from the S3 bucket."""
    log.info("Fetching Senate trades from S3: %s", SENATE_S3_URL)
    try:
        resp = requests.get(
            SENATE_S3_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        raw_data = resp.json()
    except requests.RequestException as exc:
        log.error("Failed to fetch Senate S3 data: %s", exc)
        return []

    if not isinstance(raw_data, list):
        log.warning("Senate S3 response is not a list; got %s", type(raw_data).__name__)
        return []

    trades: list[dict[str, Any]] = []
    for record in raw_data:
        normalised = _normalise_senate_trade(record)
        if normalised is not None:
            trades.append(normalised)

    log.info("Normalised %d Senate trades from %d raw records", len(trades), len(raw_data))
    return trades


def deduplicate(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate trades by ID.
    If two trades share the same ID (same politician+date+ticker+type+amount),
    keep the one with the later disclosure_date (presumed amended).
    """
    seen: dict[str, dict[str, Any]] = {}
    for trade in trades:
        tid = trade["id"]
        if tid not in seen:
            seen[tid] = trade
        else:
            existing = seen[tid]
            # Keep the more recently disclosed (amended) filing
            if trade.get("disclosure_date", "") > existing.get("disclosure_date", ""):
                trade["is_amended"] = True
                seen[tid] = trade
            else:
                existing["is_amended"] = True

    deduped = list(seen.values())
    removed = len(trades) - len(deduped)
    if removed:
        log.info("Deduplication removed %d duplicate trades", removed)
    return deduped


def fetch_all() -> list[dict[str, Any]]:
    """
    Main entry point: fetch from both S3 sources, normalise, deduplicate,
    and persist to disk.
    """
    house_trades = fetch_house_s3()
    senate_trades = fetch_senate_s3()

    combined = house_trades + senate_trades
    log.info("Combined total before dedup: %d trades", len(combined))

    # Write raw intermediate file
    try:
        with open(TRADES_RAW_JSON, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2, default=str)
        log.info("Wrote raw trades to %s", TRADES_RAW_JSON)
    except OSError as exc:
        log.error("Could not write raw trades file: %s", exc)

    # Deduplicate
    trades = deduplicate(combined)

    # Sort by transaction date descending (most recent first)
    trades.sort(key=lambda t: t.get("tx_date", ""), reverse=True)

    # Write final trades file
    try:
        with open(TRADES_JSON, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, default=str)
        log.info("Wrote %d trades to %s", len(trades), TRADES_JSON)
    except OSError as exc:
        log.error("Could not write trades file: %s", exc)

    return trades


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Starting S3 data fetch...")
    result = fetch_all()
    log.info("Done. Total trades: %d", len(result))
    sys.exit(0)
