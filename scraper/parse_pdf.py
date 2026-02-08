"""
DC-Watcher: PDF parsing utility.

Extracts stock trade transactions from congressional Financial Disclosure
PDFs using pdfplumber.  Handles the common table layouts found in both
House and Senate Periodic Transaction Report PDFs.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

from config import AMOUNT_RANGES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("parse_pdf")


# ---------------------------------------------------------------------------
# Expected column headers (case-insensitive matching)
# ---------------------------------------------------------------------------

# House PTR PDFs typically have these columns:
HOUSE_COLUMNS = [
    "owner",
    "asset",
    "transaction type",
    "date",
    "notification date",
    "amount",
    "cap gains",
]

# Senate PTR PDFs typically have:
SENATE_COLUMNS = [
    "owner",
    "ticker",
    "asset name",
    "asset type",
    "transaction type",
    "date",
    "amount",
    "comment",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str | None) -> str:
    """Strip and collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw: str) -> str:
    """Try to parse a date string into YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _parse_amount(raw: str) -> tuple[int, int]:
    """Map an amount string to (low, high)."""
    raw = raw.strip()
    if raw in AMOUNT_RANGES:
        return AMOUNT_RANGES[raw]
    # Try fuzzy match
    for key, val in AMOUNT_RANGES.items():
        if key.split(" -")[0] in raw:
            return val
    # Try numeric extraction
    nums = re.findall(r"[\d,]+", raw)
    if len(nums) >= 2:
        try:
            return (int(nums[0].replace(",", "")), int(nums[1].replace(",", "")))
        except ValueError:
            pass
    return (0, 0)


def _normalise_tx_type(raw: str) -> str:
    """Normalise transaction type."""
    t = raw.lower()
    if "sale" in t and "full" in t:
        return "sale_full"
    if "sale" in t and "partial" in t:
        return "sale_partial"
    if "sale" in t:
        return "sale_partial"
    if "exchange" in t:
        return "exchange"
    return "purchase"


def _detect_asset_type(description: str) -> str:
    """Detect asset type from description."""
    d = description.lower()
    if any(kw in d for kw in ("option", "call", "put")):
        return "option"
    if any(kw in d for kw in ("etf", "exchange traded", "exchange-traded")):
        return "etf"
    if any(kw in d for kw in ("bond", "treasury", "note", "municipal")):
        return "bond"
    return "stock"


def _normalise_owner(raw: str) -> str:
    """Normalise owner field."""
    o = raw.lower()
    if "spouse" in o or "sp" == o:
        return "spouse"
    if "joint" in o or "jt" == o:
        return "joint"
    if "dependent" in o or "dc" == o or "child" in o:
        return "dependent"
    return "self"


def _extract_ticker(text: str) -> str:
    """Try to extract a stock ticker from a text string."""
    # Look for patterns like (AAPL) or [AAPL] or "AAPL -"
    m = re.search(r"[(\[]\s*([A-Z]{1,5})\s*[)\]]", text)
    if m:
        return m.group(1)
    # Look for standalone ticker-like patterns at the start
    m = re.match(r"^([A-Z]{1,5})\s*[-:]", text)
    if m:
        return m.group(1)
    return ""


def _make_trade_id(
    politician: str,
    tx_date: str,
    ticker: str,
    tx_type: str,
    amount_low: int,
    amount_high: int,
) -> str:
    """Generate deterministic trade ID."""
    raw = f"{politician}|{tx_date}|{ticker}|{tx_type}|{amount_low}|{amount_high}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------

def _find_best_table(tables: list, expected_cols: int = 5) -> list | None:
    """
    From a list of pdfplumber tables, find the one that most likely
    contains transaction data (based on column count and header matching).
    """
    if not tables:
        return None

    best = None
    best_score = 0

    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [_clean(c).lower() for c in table[0] if c]
        header_text = " ".join(header)

        score = 0
        if "transaction" in header_text:
            score += 3
        if "asset" in header_text:
            score += 2
        if "amount" in header_text:
            score += 2
        if "date" in header_text:
            score += 1
        if "owner" in header_text:
            score += 1
        if len(table[0]) >= expected_cols:
            score += 1

        if score > best_score:
            best_score = score
            best = table

    return best


def _map_columns(header_row: list[str | None]) -> dict[str, int]:
    """
    Map column names in a table header to their indices.
    Returns a dict like {"asset": 1, "transaction_type": 2, ...}.
    """
    mapping: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        h = _clean(cell).lower()

        if "owner" in h:
            mapping["owner"] = i
        elif "ticker" in h or "symbol" in h:
            mapping["ticker"] = i
        elif "asset" in h and "type" in h:
            mapping["asset_type"] = i
        elif "asset" in h:
            mapping["asset"] = i
        elif "transaction" in h and "type" in h:
            mapping["tx_type"] = i
        elif "transaction" in h and "date" in h:
            mapping["tx_date"] = i
        elif "notification" in h or "disclosure" in h:
            mapping["disclosure_date"] = i
        elif "date" in h:
            mapping["tx_date"] = i
        elif "amount" in h:
            mapping["amount"] = i
        elif "type" in h:
            mapping["tx_type"] = i
        elif "comment" in h or "description" in h:
            mapping["comment"] = i

    return mapping


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_disclosure_pdf(
    pdf_path: str | Path,
    politician: str = "",
    chamber: str = "house",
    party: str = "",
    state: str = "",
    filing_url: str = "",
) -> list[dict[str, Any]]:
    """
    Parse a congressional Financial Disclosure PDF and extract trade data.

    Args:
        pdf_path: Path to the PDF file.
        politician: Name of the politician (if known from metadata).
        chamber: "house" or "senate".
        party: Party affiliation.
        state: State abbreviation.
        filing_url: URL where the PDF was obtained.

    Returns:
        List of trade dicts in the unified schema.
    """
    if pdfplumber is None:
        log.error("pdfplumber is not installed; cannot parse PDFs")
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        return []

    log.info("Parsing PDF: %s", pdf_path)
    trades: list[dict[str, Any]] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_tables: list = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    all_tables.extend(page_tables)

            if not all_tables:
                log.warning("No tables found in %s", pdf_path.name)
                return trades

            log.info("Found %d tables across %d pages", len(all_tables), len(pdf.pages))

            # Process each table that looks like it contains transactions
            for table in all_tables:
                if not table or len(table) < 2:
                    continue

                col_map = _map_columns(table[0])
                if "tx_type" not in col_map and "amount" not in col_map:
                    # Doesn't look like a transaction table
                    continue

                for row in table[1:]:
                    trade = _parse_table_row(
                        row, col_map, politician, chamber, party, state, filing_url
                    )
                    if trade:
                        trades.append(trade)

    except Exception as exc:
        log.error("Error parsing PDF %s: %s", pdf_path.name, exc)

    log.info("Extracted %d trades from %s", len(trades), pdf_path.name)
    return trades


def _parse_table_row(
    row: list[str | None],
    col_map: dict[str, int],
    politician: str,
    chamber: str,
    party: str,
    state: str,
    filing_url: str,
) -> dict[str, Any] | None:
    """Parse a single table row into a trade dict."""
    def _get(key: str) -> str:
        idx = col_map.get(key, -1)
        if idx < 0 or idx >= len(row):
            return ""
        return _clean(row[idx])

    # Extract fields
    asset_desc = _get("asset")
    tx_type_raw = _get("tx_type")
    amount_raw = _get("amount")
    tx_date_raw = _get("tx_date")
    disclosure_date_raw = _get("disclosure_date")
    owner_raw = _get("owner")
    ticker_raw = _get("ticker")

    # Skip empty rows
    if not asset_desc and not tx_type_raw and not amount_raw:
        return None

    # Derive ticker from asset description if not in a dedicated column
    ticker = ticker_raw.upper() if ticker_raw else _extract_ticker(asset_desc)
    if ticker in ("N/A", "--"):
        ticker = ""

    tx_type = _normalise_tx_type(tx_type_raw)
    tx_date = _parse_date(tx_date_raw)
    disclosure_date = _parse_date(disclosure_date_raw)
    amount_low, amount_high = _parse_amount(amount_raw)
    owner = _normalise_owner(owner_raw)
    asset_type = _detect_asset_type(asset_desc)

    trade_id = _make_trade_id(politician, tx_date, ticker, tx_type, amount_low, amount_high)

    # Calculate days late
    days_late = 0
    if tx_date and disclosure_date:
        try:
            from datetime import date as date_cls
            td = date_cls.fromisoformat(tx_date)
            dd = date_cls.fromisoformat(disclosure_date)
            days_late = max(0, (dd - td).days - 45)
        except (ValueError, TypeError):
            pass

    return {
        "id": trade_id,
        "politician": politician,
        "party": party,
        "state": state,
        "chamber": chamber,
        "ticker": ticker,
        "asset_description": asset_desc,
        "asset_type": asset_type,
        "tx_type": tx_type,
        "tx_date": tx_date,
        "disclosure_date": disclosure_date,
        "amount_low": amount_low,
        "amount_high": amount_high,
        "owner": owner,
        "filing_url": filing_url,
        "is_amended": False,
        "days_late": days_late,
    }


# Convenience aliases
parse_house_pdf = parse_disclosure_pdf
parse_senate_pdf = parse_disclosure_pdf


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Parse a disclosure PDF")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--politician", default="", help="Politician name")
    parser.add_argument("--chamber", default="house", choices=["house", "senate"])
    parser.add_argument("--party", default="", help="Party (D/R/I)")
    parser.add_argument("--state", default="", help="State abbreviation")
    args = parser.parse_args()

    trades = parse_disclosure_pdf(
        args.pdf,
        politician=args.politician,
        chamber=args.chamber,
        party=args.party,
        state=args.state,
    )

    print(json.dumps(trades, indent=2))
    log.info("Parsed %d trades from %s", len(trades), args.pdf)
