"""
DC-Watcher: Fallback Senate disclosure scraper.

Searches for Periodic Transaction Report (PTR) filings from the
Senate's Electronic Financial Disclosures (EFD) system. This is a
fallback source -- the primary feed comes from fetch_s3_data.py.

The Senate EFD site requires accepting a usage agreement before
searching, so we handle that via a session with cookie persistence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import (
    AMOUNT_RANGES,
    DATA_DIR,
    REQUEST_TIMEOUT,
    TRADES_JSON,
    USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scrape_senate")

SENATE_EFD_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SENATE_EFD_AGREEMENT = "https://efts.sec.gov/LATEST/search-index"
SENATE_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# Alternative: Senate's own eFD portal
SENATE_EFD_HOME = "https://efdsearch.senate.gov"
SENATE_EFD_AGREE = f"{SENATE_EFD_HOME}/search/home/"
SENATE_EFD_SEARCH_API = f"{SENATE_EFD_HOME}/search/"
SENATE_EFD_REPORT = f"{SENATE_EFD_HOME}/search/view/ptr/"

SENATE_META_JSON = DATA_DIR / "senate_filings_meta.json"


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_senate_session() -> requests.Session:
    """
    Create an HTTP session and accept the Senate eFD agreement.
    The site sets a CSRF token cookie that must be sent back as a header.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    # Step 1: GET the agreement page to obtain CSRF token
    log.info("Fetching Senate eFD agreement page...")
    try:
        resp = session.get(SENATE_EFD_AGREE, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to load eFD agreement page: %s", exc)
        return session

    # Extract CSRF token
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf_token = csrf_input["value"] if csrf_input else ""

    if not csrf_token:
        # Try from cookies
        csrf_token = session.cookies.get("csrftoken", "")

    if not csrf_token:
        log.warning("Could not find CSRF token; search may fail")
        return session

    # Step 2: POST to accept agreement
    log.info("Accepting Senate eFD agreement...")
    try:
        resp = session.post(
            SENATE_EFD_AGREE,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "prohibition_agreement": "1",
            },
            headers={
                "Referer": SENATE_EFD_AGREE,
                "X-CSRFToken": csrf_token,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        log.info("Agreement accepted (status %d)", resp.status_code)
    except requests.RequestException as exc:
        log.error("Failed to accept agreement: %s", exc)

    return session


# ---------------------------------------------------------------------------
# Search for PTR filings
# ---------------------------------------------------------------------------

def search_ptr_filings(
    session: requests.Session,
    first_name: str = "",
    last_name: str = "",
    days_back: int = 90,
) -> list[dict[str, Any]]:
    """
    Search the Senate eFD for Periodic Transaction Reports.

    Args:
        session: Authenticated session (from create_senate_session).
        first_name: Optional filter by senator first name.
        last_name: Optional filter by senator last name.
        days_back: How many days back to search.

    Returns:
        List of filing metadata dicts.
    """
    csrf_token = session.cookies.get("csrftoken", "")

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    date_to = datetime.now().strftime("%m/%d/%Y")

    payload = {
        "csrfmiddlewaretoken": csrf_token,
        "first_name": first_name,
        "last_name": last_name,
        "filer_type": "1",  # Senator
        "report_type": "11",  # Periodic Transaction Report
        "date_start": date_from,
        "date_end": date_to,
        "submitted": "1",
    }

    log.info(
        "Searching Senate PTR filings from %s to %s (name: %s %s)",
        date_from, date_to, first_name, last_name,
    )

    try:
        resp = session.post(
            SENATE_EFD_SEARCH_API,
            data=payload,
            headers={
                "Referer": SENATE_EFD_SEARCH_API,
                "X-CSRFToken": csrf_token,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Senate PTR search failed: %s", exc)
        return []

    return parse_search_results(resp.text)


def parse_search_results(html: str) -> list[dict[str, Any]]:
    """
    Parse the HTML search results table from the Senate eFD portal.
    Returns a list of filing metadata dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    filings: list[dict[str, Any]] = []

    table = soup.find("table", class_="table")
    if not table:
        # Try alternative selectors
        table = soup.find("table")

    if not table:
        log.warning("No results table found in search response")
        return filings

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # Typical columns: Name, Office, Report Type, Date Filed, Link
        name = cells[0].get_text(strip=True)
        office = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        report_type = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        date_filed = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        # Extract link to the full report
        link_tag = row.find("a", href=True)
        report_url = ""
        report_id = ""
        if link_tag:
            href = link_tag["href"]
            report_url = href if href.startswith("http") else f"{SENATE_EFD_HOME}{href}"
            # Try to extract report ID from URL
            id_match = re.search(r"/ptr/(\w+)/", href)
            if id_match:
                report_id = id_match.group(1)

        filings.append({
            "name": name,
            "office": office,
            "report_type": report_type,
            "date_filed": date_filed,
            "report_url": report_url,
            "report_id": report_id,
        })

    log.info("Parsed %d filing records from search results", len(filings))
    return filings


# ---------------------------------------------------------------------------
# Parse detailed report (stub)
# ---------------------------------------------------------------------------

def _normalize_tx_type(raw: str) -> str:
    """Normalize a Senate transaction type string to our unified schema."""
    raw_lower = raw.strip().lower()
    if "purchase" in raw_lower:
        return "purchase"
    if "sale" in raw_lower and "full" in raw_lower:
        return "sale_full"
    if "sale" in raw_lower and "partial" in raw_lower:
        return "sale_partial"
    if "sale" in raw_lower:
        return "sale_full"
    if "exchange" in raw_lower:
        return "exchange"
    return raw.strip().lower()


def _parse_amount(amount_str: str) -> tuple[int, int]:
    """Parse an amount range string into (low, high) using AMOUNT_RANGES."""
    amount_str = amount_str.strip()
    if amount_str in AMOUNT_RANGES:
        return AMOUNT_RANGES[amount_str]
    # Try partial matching
    for key, (low, high) in AMOUNT_RANGES.items():
        if key in amount_str or amount_str in key:
            return (low, high)
    return (0, 0)


def _parse_senate_date(date_str: str) -> str:
    """Parse a Senate date string into YYYY-MM-DD format."""
    date_str = date_str.strip()
    if not date_str:
        return ""
    # Try common formats
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def fetch_report_detail(
    session: requests.Session,
    report_url: str,
    senator_name: str = "",
) -> list[dict[str, Any]]:
    """
    Fetch and parse a detailed Senate PTR report page.

    Parses the transactions table and normalizes each row into
    the unified trade schema.

    Args:
        session: Authenticated session.
        report_url: URL of the PTR report page.
        senator_name: Name of the senator (from filing metadata).

    Returns:
        List of trade dicts in the unified schema.
    """
    log.info("Fetching report detail: %s", report_url)
    try:
        resp = session.get(
            report_url,
            timeout=REQUEST_TIMEOUT,
            headers={"Referer": SENATE_EFD_SEARCH_API},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to fetch report %s: %s", report_url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    trades: list[dict[str, Any]] = []

    # Try to extract senator name from the page if not provided
    if not senator_name:
        # Look for the name in page header or title
        h1 = soup.find("h1")
        if h1:
            senator_name = h1.get_text(strip=True)
        else:
            title = soup.find("title")
            if title:
                senator_name = title.get_text(strip=True)

    # Find the transactions table
    table = None
    # Try finding a table with class containing "table"
    table = soup.find("table", class_=re.compile(r"table", re.I))
    if not table:
        # Try finding by looking for header keywords
        for tbl in soup.find_all("table"):
            header_text = tbl.get_text(strip=True).lower()
            if any(kw in header_text for kw in ("transaction date", "ticker", "asset name", "transaction type")):
                table = tbl
                break
    if not table:
        # Last resort: just grab the first table
        table = soup.find("table")

    if not table:
        log.warning("No transactions table found on report page: %s", report_url)
        return []

    # Determine column indices from header row
    header_row = table.find("thead")
    if header_row:
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]
    else:
        first_row = table.find("tr")
        if first_row:
            headers = [cell.get_text(strip=True).lower() for cell in first_row.find_all(["th", "td"])]
        else:
            headers = []

    # Map column indices
    col_map: dict[str, int] = {}
    header_keywords = {
        "tx_date": ["transaction date", "date"],
        "owner": ["owner"],
        "ticker": ["ticker", "symbol"],
        "asset_name": ["asset name", "asset", "name", "description"],
        "tx_type": ["transaction type", "type", "transaction"],
        "amount": ["amount"],
    }
    for field, keywords in header_keywords.items():
        for i, h in enumerate(headers):
            for kw in keywords:
                if kw in h and field not in col_map:
                    col_map[field] = i
                    break

    # Parse rows
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        def get_cell(field: str, default: str = "") -> str:
            idx = col_map.get(field)
            if idx is not None and idx < len(cells):
                return cells[idx].get_text(strip=True)
            return default

        tx_date_raw = get_cell("tx_date")
        owner = get_cell("owner")
        ticker = get_cell("ticker")
        asset_name = get_cell("asset_name")
        tx_type_raw = get_cell("tx_type")
        amount_raw = get_cell("amount")

        # If column mapping failed, try positional fallback
        # Typical order: Date, Owner, Ticker, Asset Name, Type, Amount
        if not ticker and len(cells) >= 6:
            tx_date_raw = cells[0].get_text(strip=True)
            owner = cells[1].get_text(strip=True)
            ticker = cells[2].get_text(strip=True)
            asset_name = cells[3].get_text(strip=True)
            tx_type_raw = cells[4].get_text(strip=True)
            amount_raw = cells[5].get_text(strip=True)

        # Normalize fields
        tx_date = _parse_senate_date(tx_date_raw)
        tx_type = _normalize_tx_type(tx_type_raw)
        amount_low, amount_high = _parse_amount(amount_raw)

        # Clean up ticker (remove leading/trailing whitespace, -- means no ticker)
        ticker = ticker.strip().replace("--", "").replace("N/A", "").strip()

        # Generate trade ID
        trade_id = hashlib.sha256(
            f"{senator_name}{tx_date}{ticker}{tx_type}{amount_low}{amount_high}".encode()
        ).hexdigest()[:16]

        trades.append({
            "id": trade_id,
            "politician": senator_name,
            "party": "",  # Senate party info not always on PTR page
            "state": "",
            "chamber": "senate",
            "ticker": ticker,
            "asset_description": asset_name,
            "asset_type": "stock",
            "tx_type": tx_type,
            "tx_date": tx_date,
            "disclosure_date": "",
            "amount_low": amount_low,
            "amount_high": amount_high,
            "owner": owner,
            "filing_url": report_url,
            "is_amended": False,
            "days_late": 0,
        })

    log.info("Parsed %d transactions from report: %s", len(trades), report_url)
    return trades


# ---------------------------------------------------------------------------
# Merge senate trades into trades.json
# ---------------------------------------------------------------------------

def merge_senate_trades() -> None:
    """
    Load existing trades.json, fetch all report details from
    senate_filings_meta.json, deduplicate by trade ID, and save back.
    """
    # Load existing trades
    existing_trades: list[dict[str, Any]] = []
    if TRADES_JSON.exists():
        try:
            with open(TRADES_JSON, "r", encoding="utf-8") as f:
                existing_trades = json.load(f)
            log.info("Loaded %d existing trades from %s", len(existing_trades), TRADES_JSON)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not load existing trades.json: %s", exc)

    # Load senate filing metadata
    if not SENATE_META_JSON.exists():
        log.warning("No senate filings metadata found at %s", SENATE_META_JSON)
        return

    try:
        with open(SENATE_META_JSON, "r", encoding="utf-8") as f:
            filings = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Could not load senate filings metadata: %s", exc)
        return

    # Fetch details for each filing
    session = create_senate_session()
    new_trades: list[dict[str, Any]] = []

    for filing in filings:
        report_url = filing.get("report_url", "")
        senator_name = filing.get("name", "")
        if not report_url:
            continue

        detail_trades = fetch_report_detail(session, report_url, senator_name=senator_name)
        new_trades.extend(detail_trades)
        time.sleep(0.5)  # Rate limit between requests

    log.info("Fetched %d new senate trades from %d filings", len(new_trades), len(filings))

    # Deduplicate by trade ID
    existing_ids = {t.get("id", "") for t in existing_trades if t.get("id")}
    added = 0
    for trade in new_trades:
        if trade.get("id") and trade["id"] not in existing_ids:
            existing_trades.append(trade)
            existing_ids.add(trade["id"])
            added += 1

    log.info("Added %d new unique senate trades (total: %d)", added, len(existing_trades))

    # Save back
    try:
        with open(TRADES_JSON, "w", encoding="utf-8") as f:
            json.dump(existing_trades, f, indent=2, default=str)
        log.info("Wrote merged trades to %s", TRADES_JSON)
    except OSError as exc:
        log.error("Could not write trades.json: %s", exc)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run(
    first_name: str = "",
    last_name: str = "",
    days_back: int = 90,
) -> list[dict[str, Any]]:
    """Search for recent Senate PTR filings, fetch details, and merge."""
    session = create_senate_session()
    filings = search_ptr_filings(
        session,
        first_name=first_name,
        last_name=last_name,
        days_back=days_back,
    )

    if filings:
        # Save metadata
        try:
            with open(SENATE_META_JSON, "w", encoding="utf-8") as f:
                json.dump(filings, f, indent=2)
            log.info("Wrote Senate filing metadata to %s", SENATE_META_JSON)
        except OSError as exc:
            log.error("Could not write Senate metadata: %s", exc)

        log.info("Sample filings:")
        for filing in filings[:5]:
            log.info(
                "  %s | %s | %s | %s",
                filing["name"],
                filing["office"],
                filing["date_filed"],
                filing["report_url"],
            )

        # Fetch report details for each filing
        all_trades: list[dict[str, Any]] = []
        for filing in filings:
            report_url = filing.get("report_url", "")
            senator_name = filing.get("name", "")
            if not report_url:
                continue
            detail_trades = fetch_report_detail(
                session, report_url, senator_name=senator_name
            )
            all_trades.extend(detail_trades)
            time.sleep(0.5)  # Rate limit between requests

        log.info("Fetched %d trades from %d filings", len(all_trades), len(filings))

        # Merge into trades.json
        merge_senate_trades()
    else:
        log.info("No filings found.")

    return filings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Senate PTR filings")
    parser.add_argument("--first", default="", help="Senator first name filter")
    parser.add_argument("--last", default="", help="Senator last name filter")
    parser.add_argument("--days", type=int, default=90, help="Days back to search")
    args = parser.parse_args()

    results = run(first_name=args.first, last_name=args.last, days_back=args.days)
    log.info("Done. Total filings found: %d", len(results))
    sys.exit(0)
