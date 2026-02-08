"""
DC-Watcher: SQLite database builder.

Reads enriched trade data from trades.json and builds a structured
SQLite database with tables for trades, politicians, and tickers,
plus indexes for common query patterns.

Output: data/dc-watcher.db
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from config import DB_PATH, TRADES_JSON

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("build_db")


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    id               TEXT PRIMARY KEY,
    politician       TEXT NOT NULL,
    party            TEXT DEFAULT '',
    state            TEXT DEFAULT '',
    chamber          TEXT DEFAULT '',
    ticker           TEXT DEFAULT '',
    asset_description TEXT DEFAULT '',
    asset_type       TEXT DEFAULT 'stock',
    tx_type          TEXT DEFAULT 'purchase',
    tx_date          TEXT DEFAULT '',
    disclosure_date  TEXT DEFAULT '',
    amount_low       INTEGER DEFAULT 0,
    amount_high      INTEGER DEFAULT 0,
    est_position     INTEGER DEFAULT 0,
    owner            TEXT DEFAULT 'self',
    filing_url       TEXT DEFAULT '',
    is_amended       INTEGER DEFAULT 0,
    days_late        INTEGER DEFAULT 0,
    price_at_trade   REAL,
    current_price    REAL,
    est_return       REAL
);
"""

POLITICIANS_TABLE = """
CREATE TABLE IF NOT EXISTS politicians (
    name             TEXT PRIMARY KEY,
    party            TEXT DEFAULT '',
    state            TEXT DEFAULT '',
    chamber          TEXT DEFAULT '',
    total_trades     INTEGER DEFAULT 0,
    trades_with_returns INTEGER DEFAULT 0,
    est_return_1y    REAL DEFAULT 0.0,
    win_rate         REAL DEFAULT 0.0,
    unique_tickers   INTEGER DEFAULT 0
);
"""

TICKERS_TABLE = """
CREATE TABLE IF NOT EXISTS tickers (
    ticker           TEXT PRIMARY KEY,
    company_name     TEXT DEFAULT '',
    sector           TEXT DEFAULT '',
    trade_count      INTEGER DEFAULT 0,
    purchase_count   INTEGER DEFAULT 0,
    sale_count       INTEGER DEFAULT 0,
    politician_count INTEGER DEFAULT 0
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_trades_politician ON trades(politician);",
    "CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_trades_tx_date ON trades(tx_date);",
    "CREATE INDEX IF NOT EXISTS idx_trades_party ON trades(party);",
    "CREATE INDEX IF NOT EXISTS idx_trades_chamber ON trades(chamber);",
    "CREATE INDEX IF NOT EXISTS idx_trades_tx_type ON trades(tx_type);",
    "CREATE INDEX IF NOT EXISTS idx_trades_disclosure_date ON trades(disclosure_date);",
    "CREATE INDEX IF NOT EXISTS idx_politicians_party ON politicians(party);",
    "CREATE INDEX IF NOT EXISTS idx_politicians_chamber ON politicians(chamber);",
    "CREATE INDEX IF NOT EXISTS idx_politicians_return ON politicians(est_return_1y);",
]


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes."""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS trades;")
    cursor.execute("DROP TABLE IF EXISTS politicians;")
    cursor.execute("DROP TABLE IF EXISTS tickers;")
    cursor.execute(TRADES_TABLE)
    cursor.execute(POLITICIANS_TABLE)
    cursor.execute(TICKERS_TABLE)
    for idx_sql in INDEXES:
        cursor.execute(idx_sql)
    conn.commit()
    log.info("Schema created (tables: trades, politicians, tickers)")


def insert_trades(conn: sqlite3.Connection, trades: list[dict[str, Any]]) -> int:
    """Insert all trades into the trades table. Returns count inserted."""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for trade in trades:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO trades (
                    id, politician, party, state, chamber, ticker,
                    asset_description, asset_type, tx_type, tx_date,
                    disclosure_date, amount_low, amount_high, est_position,
                    owner, filing_url, is_amended, days_late,
                    price_at_trade, current_price, est_return
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    trade.get("id", ""),
                    trade.get("politician", ""),
                    trade.get("party", ""),
                    trade.get("state", ""),
                    trade.get("chamber", ""),
                    trade.get("ticker", ""),
                    trade.get("asset_description", ""),
                    trade.get("asset_type", "stock"),
                    trade.get("tx_type", "purchase"),
                    trade.get("tx_date", ""),
                    trade.get("disclosure_date", ""),
                    trade.get("amount_low", 0),
                    trade.get("amount_high", 0),
                    trade.get("est_position", 0),
                    trade.get("owner", "self"),
                    trade.get("filing_url", ""),
                    1 if trade.get("is_amended") else 0,
                    trade.get("days_late", 0),
                    trade.get("price_at_trade"),
                    trade.get("current_price"),
                    trade.get("est_return"),
                ),
            )
            inserted += 1
        except sqlite3.Error as exc:
            log.warning("Failed to insert trade %s: %s", trade.get("id", "?"), exc)
            skipped += 1

    conn.commit()
    log.info("Inserted %d trades (%d skipped)", inserted, skipped)
    return inserted


def build_politicians_table(conn: sqlite3.Connection) -> int:
    """
    Aggregate trade data into the politicians table.
    Computed directly from the trades table via SQL.
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO politicians (
            name, party, state, chamber, total_trades,
            trades_with_returns, est_return_1y, win_rate, unique_tickers
        )
        SELECT
            politician,
            -- Take most common party/state/chamber
            MAX(party),
            MAX(state),
            MAX(chamber),
            COUNT(*) AS total_trades,
            SUM(CASE WHEN est_return IS NOT NULL THEN 1 ELSE 0 END) AS trades_with_returns,
            ROUND(COALESCE(AVG(
                CASE WHEN est_return IS NOT NULL
                     AND tx_date >= date('now', '-1 year')
                THEN est_return END
            ), 0.0), 2) AS est_return_1y,
            ROUND(COALESCE(
                100.0 * SUM(
                    CASE WHEN est_return IS NOT NULL
                         AND est_return > 0
                         AND tx_date >= date('now', '-1 year')
                    THEN 1 ELSE 0 END
                ) * 1.0 / NULLIF(SUM(
                    CASE WHEN est_return IS NOT NULL
                         AND tx_date >= date('now', '-1 year')
                    THEN 1 ELSE 0 END
                ), 0),
            0.0), 1) AS win_rate,
            COUNT(DISTINCT ticker) AS unique_tickers
        FROM trades
        WHERE politician != ''
        GROUP BY politician
        """
    )
    conn.commit()

    count = cursor.execute("SELECT COUNT(*) FROM politicians").fetchone()[0]
    log.info("Built politicians table: %d entries", count)
    return count


def build_tickers_table(conn: sqlite3.Connection) -> int:
    """
    Aggregate trade data into the tickers table.
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO tickers (
            ticker, company_name, sector, trade_count,
            purchase_count, sale_count, politician_count
        )
        SELECT
            ticker,
            MAX(asset_description) AS company_name,
            '' AS sector,
            COUNT(*) AS trade_count,
            SUM(CASE WHEN tx_type = 'purchase' THEN 1 ELSE 0 END) AS purchase_count,
            SUM(CASE WHEN tx_type IN ('sale_full', 'sale_partial') THEN 1 ELSE 0 END) AS sale_count,
            COUNT(DISTINCT politician) AS politician_count
        FROM trades
        WHERE ticker != ''
        GROUP BY ticker
        """
    )
    conn.commit()

    count = cursor.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
    log.info("Built tickers table: %d entries", count)
    return count


# ---------------------------------------------------------------------------
# Main build pipeline
# ---------------------------------------------------------------------------

def build(trades_path: Path | None = None, db_path: Path | None = None) -> None:
    """
    Full database build pipeline:
    1. Load trades from JSON
    2. Create schema
    3. Insert trades
    4. Build derived tables (politicians, tickers)
    """
    if trades_path is None:
        trades_path = TRADES_JSON
    if db_path is None:
        db_path = DB_PATH

    # Load trades
    if not trades_path.exists():
        log.error("Trades file not found: %s", trades_path)
        log.error("Run fetch_s3_data.py and enrich.py first.")
        sys.exit(1)

    try:
        with open(trades_path, "r", encoding="utf-8") as f:
            trades = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Could not load trades: %s", exc)
        sys.exit(1)

    log.info("Loaded %d trades from %s", len(trades), trades_path)

    # Build database
    log.info("Creating database at %s", db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    try:
        create_schema(conn)
        insert_trades(conn, trades)
        build_politicians_table(conn)
        build_tickers_table(conn)

        # Print summary stats
        cursor = conn.cursor()
        trade_count = cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        pol_count = cursor.execute("SELECT COUNT(*) FROM politicians").fetchone()[0]
        ticker_count = cursor.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]

        log.info("Database build complete:")
        log.info("  Trades:      %d", trade_count)
        log.info("  Politicians: %d", pol_count)
        log.info("  Tickers:     %d", ticker_count)
        log.info("  DB size:     %.1f MB", db_path.stat().st_size / 1_048_576)

    except sqlite3.Error as exc:
        log.error("Database error: %s", exc)
        sys.exit(1)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build DC-Watcher SQLite database")
    parser.add_argument(
        "--trades", type=Path, default=None,
        help="Path to trades.json (default: data/trades.json)",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Output database path (default: data/dc-watcher.db)",
    )
    args = parser.parse_args()

    build(trades_path=args.trades, db_path=args.db)
    log.info("Done.")
    sys.exit(0)
