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

SENATE_EFD_HOME = "https://efdsearch.senate.gov"
SENATE_EFD_AGREE = f"{SENATE_EFD_HOME}/search/home/"
SENATE_EFD_SEARCH_PAGE = f"{SENATE_EFD_HOME}/search/"
SENATE_EFD_DATA_API = f"{SENATE_EFD_HOME}/search/report/data/"
SENATE_EFD_REPORT = f"{SENATE_EFD_HOME}/search/view/ptr/"

# DataTables page size for the server-side AJAX endpoint
_DT_PAGE_SIZE = 100

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

def _build_datatables_params(
    start: int,
    length: int,
    first_name: str,
    last_name: str,
    filer_types: str,
    report_types: str,
    submitted_start_date: str,
    submitted_end_date: str,
) -> dict[str, str]:
    """
    Build the form-encoded payload that the Senate eFD DataTables
    server-side endpoint expects at /search/report/data/.

    The site uses jQuery DataTables 1.10 with ``serverSide: true``.
    Each AJAX request must include both the standard DataTables draw /
    paging / column / order / search parameters **and** the custom
    search fields the site appends via its ``data`` callback.
    """
    params: dict[str, str] = {
        # DataTables standard fields
        "draw": "1",
        "start": str(start),
        "length": str(length),
        # Column definitions (5 columns: first, last, office, report, date)
        "columns[0][data]": "0",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "true",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "1",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "2",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "true",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "3",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "4",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        # Default ordering: column 1 (last name) ascending
        "order[0][column]": "1",
        "order[0][dir]": "asc",
        # Global search (unused by us)
        "search[value]": "",
        "search[regex]": "false",
        # Custom site-specific search parameters
        "report_types": report_types,
        "filer_types": filer_types,
        "submitted_start_date": submitted_start_date,
        "submitted_end_date": submitted_end_date,
        "candidate_state": "",
        "senator_state": "",
        "office_id": "",
        "first_name": first_name,
        "last_name": last_name,
    }
    return params


def search_ptr_filings(
    session: requests.Session,
    first_name: str = "",
    last_name: str = "",
    days_back: int = 90,
) -> list[dict[str, Any]]:
    """
    Search the Senate eFD for Periodic Transaction Reports.

    The site uses a jQuery DataTables server-side AJAX endpoint at
    ``/search/report/data/`` that returns JSON. We paginate through
    all results automatically.

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

    log.info(
        "Searching Senate PTR filings from %s to %s (name: %s %s)",
        date_from, date_to, first_name, last_name,
    )

    filings: list[dict[str, Any]] = []
    start = 0

    while True:
        params = _build_datatables_params(
            start=start,
            length=_DT_PAGE_SIZE,
            first_name=first_name,
            last_name=last_name,
            filer_types="[1]",            # Senator
            report_types="[11]",          # Periodic Transaction Report
            submitted_start_date=f"{date_from} 00:00:00",
            submitted_end_date=f"{date_to} 23:59:59",
        )

        try:
            resp = session.post(
                SENATE_EFD_DATA_API,
                data=params,
                headers={
                    "Referer": SENATE_EFD_SEARCH_PAGE,
                    "X-CSRFToken": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error("Senate PTR search failed: %s", exc)
            break

        page_filings, total = _parse_datatables_response(resp.text)
        filings.extend(page_filings)

        log.info(
            "  Page at offset %d: got %d filings (total on server: %d)",
            start, len(page_filings), total,
        )

        if not page_filings or start + _DT_PAGE_SIZE >= total:
            break
        start += _DT_PAGE_SIZE
        time.sleep(0.3)  # polite delay between pages

    log.info("Found %d total filing records", len(filings))
    return filings


def _parse_datatables_response(body: str) -> tuple[list[dict[str, Any]], int]:
    """
    Parse the JSON response from the DataTables AJAX endpoint.

    Each row in ``data`` is a 5-element list:
        [first_name, last_name, office/title, report_link_html, date_filed]

    The report_link_html contains an ``<a>`` tag with href and text like
    ``Periodic Transaction Report for MM/DD/YYYY``.

    Returns:
        (list_of_filing_dicts, total_records_on_server)
    """
    filings: list[dict[str, Any]] = []
    total = 0

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        log.error("Senate search response was not valid JSON")
        return filings, total

    if data.get("result") != "ok":
        log.warning("Senate search returned result=%s", data.get("result"))

    total = data.get("recordsFiltered", data.get("recordsTotal", 0))
    rows = data.get("data", [])

    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            continue

        first_name = row[0].strip()
        last_name = row[1].strip()
        office = row[2].strip()
        report_html = row[3]
        date_filed = row[4].strip()

        # Combine first + last into a single name
        name = f"{first_name} {last_name}".strip()

        # Extract href and report text from the embedded <a> tag
        report_url = ""
        report_id = ""
        report_type = ""
        link_match = re.search(r'href="([^"]+)"', report_html)
        if link_match:
            href = link_match.group(1)
            report_url = href if href.startswith("http") else f"{SENATE_EFD_HOME}{href}"
            # Extract report ID from URL (works for both /ptr/<id>/ and /paper/<id>/)
            id_match = re.search(r"/(?:ptr|paper)/([\w-]+)/", href)
            if id_match:
                report_id = id_match.group(1)

        # Extract the link text for report type description
        text_match = re.search(r">([^<]+)</a>", report_html)
        if text_match:
            report_type = text_match.group(1).strip()

        filings.append({
            "name": name,
            "office": office,
            "report_type": report_type,
            "date_filed": date_filed,
            "report_url": report_url,
            "report_id": report_id,
        })

    return filings, total


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
            headers={"Referer": SENATE_EFD_SEARCH_PAGE},
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
