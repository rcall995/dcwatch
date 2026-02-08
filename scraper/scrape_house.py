"""
DC-Watcher: Fallback House disclosure scraper.

Downloads annual Financial Disclosure ZIP files from the House Clerk's
website, parses the enclosed XML for document metadata, and provides
functions to identify trades missing from the S3 data.

This is a *fallback* source -- the primary feed comes from fetch_s3_data.py.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from config import (
    DATA_DIR,
    HOUSE_DISCLOSURE_BASE,
    REQUEST_TIMEOUT,
    TRADES_JSON,
    USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scrape_house")

HOUSE_ZIP_DIR = DATA_DIR / "house_zips"
HOUSE_ZIP_DIR.mkdir(exist_ok=True)

HOUSE_META_JSON = DATA_DIR / "house_filings_meta.json"


# ---------------------------------------------------------------------------
# Download and unzip
# ---------------------------------------------------------------------------

def download_fd_zip(year: int | None = None) -> Path | None:
    """
    Download the annual Financial Disclosure ZIP from the House Clerk.
    URL pattern: https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP
    Returns path to the downloaded ZIP, or None on failure.
    """
    if year is None:
        year = datetime.now().year

    url = f"{HOUSE_DISCLOSURE_BASE}/public_disc/financial-pdfs/{year}FD.ZIP"
    dest = HOUSE_ZIP_DIR / f"{year}FD.ZIP"

    log.info("Downloading House FD ZIP for %d from %s", year, url)
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT * 2,
            headers={"User-Agent": USER_AGENT},
            stream=True,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to download House ZIP for %d: %s", year, exc)
        return None

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    log.info("Saved ZIP to %s (%.1f MB)", dest, dest.stat().st_size / 1_048_576)
    return dest


def parse_fd_xml(zip_path: Path) -> list[dict[str, Any]]:
    """
    Open the FD ZIP and parse the XML index file inside it.
    Returns a list of filing metadata dicts.
    """
    filings: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                log.warning("No XML files found in %s", zip_path)
                return filings

            for xml_name in xml_names:
                log.info("Parsing XML: %s", xml_name)
                with zf.open(xml_name) as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    for member in root.iter("Member"):
                        filing = _parse_member_element(member)
                        if filing:
                            filings.append(filing)

    except (zipfile.BadZipFile, ET.ParseError) as exc:
        log.error("Error parsing ZIP/XML %s: %s", zip_path, exc)
    except OSError as exc:
        log.error("OS error reading %s: %s", zip_path, exc)

    log.info("Parsed %d filing records from %s", len(filings), zip_path.name)
    return filings


def _parse_member_element(elem: ET.Element) -> dict[str, Any] | None:
    """Extract metadata from a single <Member> XML element."""
    prefix = elem.findtext("Prefix", "").strip()
    last = elem.findtext("Last", "").strip()
    first = elem.findtext("First", "").strip()
    suffix = elem.findtext("Suffix", "").strip()

    if not last:
        return None

    name = f"{first} {last}".strip()
    if prefix:
        name = f"{prefix} {name}"
    if suffix:
        name = f"{name} {suffix}"

    doc_id = elem.findtext("DocID", "").strip()
    filing_type = elem.findtext("FilingType", "").strip()  # P = PTR
    filing_date = elem.findtext("FilingDate", "").strip()
    state_dst = elem.findtext("StateDst", "").strip()
    year = elem.findtext("Year", "").strip()

    # Build the PDF link
    pdf_url = ""
    if doc_id:
        pdf_url = f"{HOUSE_DISCLOSURE_BASE}/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

    return {
        "name": name,
        "doc_id": doc_id,
        "filing_type": filing_type,
        "filing_date": filing_date,
        "state_district": state_dst,
        "year": year,
        "pdf_url": pdf_url,
    }


# ---------------------------------------------------------------------------
# Find gaps (filings not in S3 data)
# ---------------------------------------------------------------------------

def load_known_ids() -> set[str]:
    """Load the set of trade IDs already in trades.json."""
    if not TRADES_JSON.exists():
        return set()
    try:
        with open(TRADES_JSON, "r", encoding="utf-8") as f:
            trades = json.load(f)
        return {t["id"] for t in trades if "id" in t}
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not load existing trades: %s", exc)
        return set()


def find_missing_filings(
    filings: list[dict[str, Any]],
    known_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Compare parsed House filings against known S3 data.
    Returns filings that may contain trades we don't have yet.

    NOTE: This is a coarse comparison by filing metadata since the ZIP
    does not contain actual trade-level data -- it only has the PDF
    document index.  The actual trades live inside the PDFs.
    """
    if known_ids is None:
        known_ids = load_known_ids()

    # For now, flag all PTR filings whose doc_id we haven't processed
    processed_docs_file = DATA_DIR / "processed_house_docs.json"
    processed: set[str] = set()
    if processed_docs_file.exists():
        try:
            with open(processed_docs_file, "r", encoding="utf-8") as f:
                processed = set(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    missing = []
    for filing in filings:
        if filing.get("filing_type") != "P":
            continue  # only Periodic Transaction Reports
        doc_id = filing.get("doc_id", "")
        if doc_id and doc_id not in processed:
            missing.append(filing)

    log.info(
        "Found %d potentially new PTR filings out of %d total",
        len(missing),
        len(filings),
    )
    return missing


# ---------------------------------------------------------------------------
# PDF download stub
# ---------------------------------------------------------------------------

def download_ptr_pdf(pdf_url: str, dest_dir: Path | None = None) -> Path | None:
    """
    Download a single PTR PDF from the House disclosure site.

    TODO: Implement full gap-filling pipeline:
    1. Download the PDF
    2. Pass to parse_pdf.parse_house_pdf()
    3. Merge resulting trades into trades.json
    """
    if dest_dir is None:
        dest_dir = DATA_DIR / "house_pdfs"
        dest_dir.mkdir(exist_ok=True)

    filename = pdf_url.rsplit("/", 1)[-1]
    dest = dest_dir / filename

    if dest.exists():
        log.debug("PDF already downloaded: %s", dest)
        return dest

    log.info("Downloading PTR PDF: %s", pdf_url)
    try:
        resp = requests.get(
            pdf_url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to download PDF %s: %s", pdf_url, exc)
        return None

    with open(dest, "wb") as f:
        f.write(resp.content)

    log.info("Saved PDF to %s (%.1f KB)", dest, len(resp.content) / 1024)
    return dest


# ---------------------------------------------------------------------------
# CLI: download this year's ZIP, parse it, report stats
# ---------------------------------------------------------------------------

def run(year: int | None = None) -> list[dict[str, Any]]:
    """Download, parse, and report on House FD filings for the given year."""
    zip_path = download_fd_zip(year)
    if zip_path is None:
        log.error("No ZIP downloaded; aborting.")
        return []

    filings = parse_fd_xml(zip_path)
    if not filings:
        log.warning("No filings parsed from ZIP.")
        return filings

    # Save metadata
    try:
        with open(HOUSE_META_JSON, "w", encoding="utf-8") as f:
            json.dump(filings, f, indent=2)
        log.info("Wrote filing metadata to %s", HOUSE_META_JSON)
    except OSError as exc:
        log.error("Could not write metadata file: %s", exc)

    # Report on gaps
    missing = find_missing_filings(filings)
    if missing:
        log.info("Sample missing filings:")
        for m in missing[:5]:
            log.info("  %s | %s | %s", m["name"], m["filing_date"], m["pdf_url"])

    return filings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape House FD filings")
    parser.add_argument("--year", type=int, default=None, help="Filing year (default: current)")
    args = parser.parse_args()

    filings = run(year=args.year)
    log.info("Done. Total filings parsed: %d", len(filings))
    sys.exit(0)
