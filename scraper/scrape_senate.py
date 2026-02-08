"""
DC-Watcher: Fallback Senate disclosure scraper.

Searches for Periodic Transaction Report (PTR) filings from the
Senate's Electronic Financial Disclosures (EFD) system. This is a
fallback source -- the primary feed comes from fetch_s3_data.py.

The Senate EFD site requires accepting a usage agreement before
searching, so we handle that via a session with cookie persistence.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import (
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

def fetch_report_detail(
    session: requests.Session,
    report_url: str,
) -> list[dict[str, Any]]:
    """
    Fetch and parse a detailed Senate PTR report page.

    TODO: Implement full parsing:
    1. GET the report page
    2. Parse the transactions table
    3. Normalise each row into the unified trade schema
    4. Return list of trade dicts

    For now, returns an empty list.
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

    # TODO: Parse the HTML table of transactions
    # soup = BeautifulSoup(resp.text, "html.parser")
    # transaction_table = soup.find("table", ...)
    # for row in transaction_table: ...

    log.warning("Report detail parsing not yet implemented; returning empty list")
    return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run(
    first_name: str = "",
    last_name: str = "",
    days_back: int = 90,
) -> list[dict[str, Any]]:
    """Search for recent Senate PTR filings and report results."""
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
