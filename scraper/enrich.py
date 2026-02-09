"""
DC-Watcher: Enrichment pipeline.

Loads trades from trades.json, enriches each with stock price data
from Yahoo Finance (via yfinance), computes estimated returns, builds
per-politician summary statistics, and writes:

  - trades.json      -- enriched trades with price fields
  - summary.json     -- leaderboard of politicians by performance
  - latest.json      -- most recent 50 trades
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore[assignment]

from config import (
    LATEST_JSON,
    PRICE_CACHE_DIR,
    SIGNALS_JSON,
    SUMMARY_JSON,
    TOP_PICKS_JSON,
    TRADES_JSON,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("enrich")

# How long to keep cached prices before refreshing (days)
CACHE_TTL_DAYS = 1

# Rate-limit: seconds between Yahoo Finance requests
YF_DELAY = 0.25


# ---------------------------------------------------------------------------
# Price cache
# ---------------------------------------------------------------------------

def _cache_path(ticker: str) -> Path:
    """Return the cache file path for a given ticker."""
    safe = ticker.replace("/", "_").replace("\\", "_")
    return PRICE_CACHE_DIR / f"{safe}.json"


def _load_price_cache(ticker: str) -> dict[str, float]:
    """
    Load cached prices for a ticker.
    Returns dict mapping date strings (YYYY-MM-DD) to closing prices.
    """
    path = _cache_path(ticker)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Check TTL on the cache metadata
        cached_at = data.get("_cached_at", "")
        if cached_at:
            try:
                ca = datetime.fromisoformat(cached_at)
                if (datetime.now() - ca).days > CACHE_TTL_DAYS:
                    # Cache for "current" price is stale; historical dates are fine
                    pass  # We still use historical entries
            except ValueError:
                pass
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_price_cache(ticker: str, prices: dict[str, float]) -> None:
    """Save price cache for a ticker."""
    path = _cache_path(ticker)
    data = dict(prices)
    data["_cached_at"] = datetime.now().isoformat()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        log.warning("Could not write price cache for %s: %s", ticker, exc)


# ---------------------------------------------------------------------------
# Yahoo Finance price lookup
# ---------------------------------------------------------------------------

def fetch_price_on_date(ticker: str, target_date: str) -> float | None:
    """
    Get the closing price for `ticker` on `target_date` (YYYY-MM-DD).
    Uses cache first, then falls back to yfinance.
    Returns None if the price cannot be determined.
    """
    if not ticker or not target_date:
        return None

    cache = _load_price_cache(ticker)
    if target_date in cache:
        return cache[target_date]

    if yf is None:
        log.debug("yfinance not installed; skipping price fetch for %s", ticker)
        return None

    try:
        dt = date.fromisoformat(target_date)
    except ValueError:
        return None

    # Fetch a small window around the target date to handle weekends/holidays
    start = dt - timedelta(days=5)
    end = dt + timedelta(days=5)

    try:
        time.sleep(YF_DELAY)
        data = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        log.warning("yfinance error for %s on %s: %s", ticker, target_date, exc)
        return None

    if data is None or data.empty:
        log.debug("No price data for %s around %s", ticker, target_date)
        return None

    # Find closest available date
    price = None
    # Handle both single and multi-level column indices from yfinance
    close_col = None
    if "Close" in data.columns:
        close_col = "Close"
    else:
        # Multi-level columns: try to find Close
        for col in data.columns:
            col_str = str(col).lower()
            if "close" in col_str:
                close_col = col
                break

    if close_col is None:
        log.debug("No 'Close' column found for %s", ticker)
        return None

    close_data = data[close_col].dropna()

    # Flatten to a simple Series if multi-level (newer yfinance returns DataFrame)
    if hasattr(close_data, "columns"):
        # It's a DataFrame; squeeze to Series
        close_data = close_data.squeeze()
    if hasattr(close_data, "empty") and close_data.empty:
        return None

    # Build a simple dict of date-string -> float for safe lookup
    price_map: dict[str, float] = {}
    for i in range(len(close_data)):
        idx = close_data.index[i]
        idx_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        val = close_data.iloc[i]
        price_map[idx_date] = float(val.iloc[0]) if hasattr(val, "iloc") else float(val)

    # Try exact date first
    if target_date in price_map:
        price = price_map[target_date]
    else:
        # Take the closest date <= target
        earlier = {d: p for d, p in price_map.items() if d <= target_date}
        if earlier:
            price = earlier[max(earlier)]
        elif price_map:
            price = price_map[min(price_map)]

    if price is not None:
        cache[target_date] = round(price, 2)
        _save_price_cache(ticker, cache)

    return round(price, 2) if price is not None else None


def fetch_current_price(ticker: str) -> float | None:
    """Get the most recent closing price for a ticker."""
    today = date.today().isoformat()
    cache = _load_price_cache(ticker)
    if today in cache:
        return cache[today]

    if yf is None:
        return None

    try:
        time.sleep(YF_DELAY)
        info = yf.Ticker(ticker)
        # Try fast info first
        price = None
        try:
            fast = info.fast_info
            price = getattr(fast, "last_price", None)
        except Exception:
            pass

        if price is None:
            hist = info.history(period="5d")
            if hist is not None and not hist.empty:
                close_col = "Close" if "Close" in hist.columns else None
                if close_col is None:
                    for col in hist.columns:
                        if "close" in str(col).lower():
                            close_col = col
                            break
                if close_col is not None:
                    val = hist[close_col].dropna().iloc[-1]
                    price = float(val.iloc[0]) if hasattr(val, "iloc") else float(val)

        if price is not None:
            price = round(price, 2)
            cache[today] = price
            _save_price_cache(ticker, cache)
            return price

    except Exception as exc:
        log.warning("Could not fetch current price for %s: %s", ticker, exc)

    return None


# ---------------------------------------------------------------------------
# Enrichment pipeline
# ---------------------------------------------------------------------------

def enrich_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Enrich each trade with:
      - price_at_trade:  closing price on tx_date
      - current_price:   latest closing price
      - est_return:      estimated return percentage
      - est_position:    midpoint of amount range
    """
    # Collect unique tickers that need price lookups
    tickers = set()
    for t in trades:
        ticker = t.get("ticker", "")
        if ticker and len(ticker) <= 6:
            tickers.add(ticker)

    log.info("Enriching %d trades across %d unique tickers", len(trades), len(tickers))

    # Pre-fetch current prices for all tickers
    current_prices: dict[str, float | None] = {}
    for i, ticker in enumerate(sorted(tickers)):
        if i % 50 == 0 and i > 0:
            log.info("  Fetched current prices for %d / %d tickers", i, len(tickers))
        current_prices[ticker] = fetch_current_price(ticker)

    log.info("Fetched current prices for %d tickers", len(tickers))

    # Enrich each trade
    enriched = 0
    for trade in trades:
        ticker = trade.get("ticker", "")
        tx_date = trade.get("tx_date", "")
        amount_low = trade.get("amount_low", 0)
        amount_high = trade.get("amount_high", 0)

        # Estimated position size (midpoint of range)
        est_position = (amount_low + amount_high) // 2 if (amount_low + amount_high) > 0 else 0
        trade["est_position"] = est_position

        if not ticker or len(ticker) > 6:
            trade["price_at_trade"] = None
            trade["current_price"] = None
            trade["est_return"] = None
            continue

        # Get prices
        price_at_trade = fetch_price_on_date(ticker, tx_date) if tx_date else None
        current_price = current_prices.get(ticker)

        trade["price_at_trade"] = price_at_trade
        trade["current_price"] = current_price

        # Calculate estimated return
        if price_at_trade and current_price and price_at_trade > 0:
            raw_return = (current_price - price_at_trade) / price_at_trade
            tx_type = trade.get("tx_type", "")
            # For sales, invert the return (they profited if price went down)
            if tx_type in ("sale_full", "sale_partial"):
                raw_return = -raw_return
            trade["est_return"] = round(raw_return * 100, 2)  # percentage
            enriched += 1
        else:
            trade["est_return"] = None

    log.info("Enriched %d / %d trades with return estimates", enriched, len(trades))
    return trades


# ---------------------------------------------------------------------------
# Summary / leaderboard builder
# ---------------------------------------------------------------------------

def build_summary(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build a per-politician summary/leaderboard:
      - total_trades, est_return_1y (average), win_rate
      - best_trade, worst_trade
      - party, state, chamber
    """
    politicians: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "name": "",
        "party": "",
        "state": "",
        "chamber": "",
        "total_trades": 0,
        "returns": [],
        "best_trade": None,
        "worst_trade": None,
        "tickers": set(),
    })

    # Only consider trades from the last ~1 year for the leaderboard
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()

    for trade in trades:
        name = trade.get("politician", "")
        if not name:
            continue

        p = politicians[name]
        p["name"] = name
        p["total_trades"] += 1

        # Keep first non-empty values for party/state/chamber
        if not p["party"] and trade.get("party"):
            p["party"] = trade["party"]
        if not p["state"] and trade.get("state"):
            p["state"] = trade["state"]
        if not p["chamber"] and trade.get("chamber"):
            p["chamber"] = trade["chamber"]

        ticker = trade.get("ticker", "")
        if ticker:
            p["tickers"].add(ticker)

        ret = trade.get("est_return")
        tx_date = trade.get("tx_date", "")

        if ret is not None and tx_date >= one_year_ago:
            p["returns"].append(ret)

            # Track best/worst
            trade_summary = {
                "ticker": ticker,
                "tx_type": trade.get("tx_type", ""),
                "tx_date": tx_date,
                "est_return": ret,
                "est_position": trade.get("est_position", 0),
            }

            if p["best_trade"] is None or ret > p["best_trade"]["est_return"]:
                p["best_trade"] = trade_summary
            if p["worst_trade"] is None or ret < p["worst_trade"]["est_return"]:
                p["worst_trade"] = trade_summary

    # Build final summary list
    summary: list[dict[str, Any]] = []
    for name, p in politicians.items():
        returns = p["returns"]
        avg_return = round(sum(returns) / len(returns), 2) if returns else 0.0
        win_rate = round(
            len([r for r in returns if r > 0]) / len(returns) * 100, 1
        ) if returns else 0.0

        summary.append({
            "name": name,
            "party": p["party"],
            "state": p["state"],
            "chamber": p["chamber"],
            "total_trades": p["total_trades"],
            "trades_with_returns": len(returns),
            "est_return_1y": avg_return,
            "win_rate": win_rate,
            "unique_tickers": len(p["tickers"]),
            "best_trade": p["best_trade"],
            "worst_trade": p["worst_trade"],
        })

    # Sort by estimated return descending
    summary.sort(key=lambda s: s["est_return_1y"], reverse=True)

    log.info("Built summary for %d politicians", len(summary))
    return summary


# ---------------------------------------------------------------------------
# Signal / cluster detection
# ---------------------------------------------------------------------------

def detect_signals(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Detect trading clusters: 3+ unique politicians trading the same ticker
    within a 10-day sliding window.

    Returns a list of Signal dicts sorted by heat_score descending.
    """
    # Group trades by ticker
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        ticker = t.get("ticker", "")
        if ticker and t.get("tx_date", ""):
            by_ticker[ticker].append(t)

    signals: list[dict[str, Any]] = []

    for ticker, ticker_trades in by_ticker.items():
        # Sort by tx_date
        ticker_trades.sort(key=lambda t: t.get("tx_date", ""))

        # Sliding window: for each trade, gather all trades within 10 days
        clusters: list[dict[str, Any]] = []
        n = len(ticker_trades)

        for i in range(n):
            anchor_date_str = ticker_trades[i].get("tx_date", "")
            try:
                anchor_date = date.fromisoformat(anchor_date_str)
            except ValueError:
                continue

            window_trades = []
            unique_politicians: set[str] = set()

            for j in range(n):
                other_date_str = ticker_trades[j].get("tx_date", "")
                try:
                    other_date = date.fromisoformat(other_date_str)
                except ValueError:
                    continue

                if 0 <= (other_date - anchor_date).days <= 10:
                    window_trades.append(ticker_trades[j])
                    pol_name = ticker_trades[j].get("politician", "")
                    if pol_name:
                        unique_politicians.add(pol_name)

            if len(unique_politicians) < 3:
                continue

            # Build cluster info
            parties = set()
            politicians_list = []
            total_volume = 0.0
            start_date = None
            end_date = None

            seen_politicians_in_cluster: set[str] = set()
            for wt in window_trades:
                pol_name = wt.get("politician", "")
                party = wt.get("party", "")
                if party:
                    parties.add(party[0].upper())  # D, R, I, etc.

                # Build politician entry (may have multiple trades per politician)
                pol_key = f"{pol_name}|{wt.get('tx_date', '')}|{wt.get('tx_type', '')}"
                if pol_key not in seen_politicians_in_cluster:
                    seen_politicians_in_cluster.add(pol_key)
                    politicians_list.append({
                        "name": pol_name,
                        "party": party,
                        "tx_type": wt.get("tx_type", ""),
                        "tx_date": wt.get("tx_date", ""),
                    })

                amount_low = wt.get("amount_low", 0) or 0
                amount_high = wt.get("amount_high", 0) or 0
                total_volume += (amount_low + amount_high) / 2

                wt_date_str = wt.get("tx_date", "")
                if wt_date_str:
                    if start_date is None or wt_date_str < start_date:
                        start_date = wt_date_str
                    if end_date is None or wt_date_str > end_date:
                        end_date = wt_date_str

            bipartisan = "D" in parties and "R" in parties
            num_politicians = len(unique_politicians)
            heat_score = (
                num_politicians * 2
                + (5 if bipartisan else 0)
                + int(math.log(total_volume + 1))
            )

            company_name = ""
            for wt in window_trades:
                desc = wt.get("asset_description", "")
                if desc:
                    company_name = desc
                    break
            if not company_name:
                company_name = ticker

            clusters.append({
                "ticker": ticker,
                "company_name": company_name,
                "politicians": politicians_list,
                "start_date": start_date or "",
                "end_date": end_date or "",
                "heat_score": heat_score,
                "bipartisan": bipartisan,
            })

        # Deduplicate overlapping clusters for same ticker: keep highest heat_score
        if clusters:
            clusters.sort(key=lambda c: c["heat_score"], reverse=True)
            kept: list[dict[str, Any]] = []
            used_ranges: list[tuple[str, str]] = []

            for cluster in clusters:
                overlaps = False
                for used_start, used_end in used_ranges:
                    # Check if date ranges overlap
                    if cluster["start_date"] <= used_end and cluster["end_date"] >= used_start:
                        overlaps = True
                        break
                if not overlaps:
                    kept.append(cluster)
                    used_ranges.append((cluster["start_date"], cluster["end_date"]))

            signals.extend(kept)

    # Sort all signals by heat_score descending
    signals.sort(key=lambda s: s["heat_score"], reverse=True)
    log.info("Detected %d trading signals/clusters", len(signals))
    return signals


# ---------------------------------------------------------------------------
# Top picks: best stocks to watch based on recent politician buying
# ---------------------------------------------------------------------------

def build_top_picks(trades: list[dict], summary: list[dict]) -> list[dict]:
    """
    Find the top 5 stocks to watch based on recent politician buying activity.

    Scoring considers:
    - Number of unique politicians buying (not selling) in last 60 days
    - Bipartisan buying (both D and R)
    - Average win rate of the politicians buying
    - Recency of trades (more recent = higher score)
    - Volume (midpoint of amount ranges)
    """
    # 1. Build lookup: politician name -> win_rate from summary
    win_rate_lookup: dict[str, float] = {}
    for s in summary:
        name = s.get("name", "")
        if name:
            win_rate_lookup[name] = s.get("win_rate", 0.0)

    # 2. Filter to purchases in the last 60 days
    today = date.today()
    cutoff = today - timedelta(days=60)
    cutoff_str = cutoff.isoformat()

    recent_purchases = [
        t for t in trades
        if t.get("tx_type") == "purchase"
        and t.get("tx_date", "") >= cutoff_str
        and t.get("ticker", "")
    ]

    # 3. Group by ticker
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for t in recent_purchases:
        by_ticker[t["ticker"]].append(t)

    # 4. Score each ticker with 2+ unique politicians buying
    candidates: list[dict] = []

    for ticker, ticker_trades in by_ticker.items():
        # Unique politicians
        politician_set: set[str] = set()
        party_set: set[str] = set()
        politician_details: list[dict] = []
        seen_politicians: set[str] = set()

        for t in ticker_trades:
            pol = t.get("politician", "")
            if pol:
                politician_set.add(pol)
                party = t.get("party", "")
                if party:
                    party_set.add(party[0].upper())

                if pol not in seen_politicians:
                    seen_politicians.add(pol)
                    politician_details.append({
                        "name": pol,
                        "party": party,
                        "tx_date": t.get("tx_date", ""),
                        "win_rate": win_rate_lookup.get(pol, 0.0),
                    })

        num_politicians = len(politician_set)
        if num_politicians < 2:
            continue

        bipartisan = "D" in party_set and "R" in party_set

        # Average win rate of buying politicians
        win_rates = [win_rate_lookup.get(p, 0.0) for p in politician_set]
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0

        # Recency score
        recency_score = 0.0
        for t in ticker_trades:
            tx_date_str = t.get("tx_date", "")
            try:
                tx_dt = date.fromisoformat(tx_date_str)
                days_ago = (today - tx_dt).days
                if days_ago <= 14:
                    recency_score += 3
                elif days_ago <= 30:
                    recency_score += 2
                else:
                    recency_score += 1
            except ValueError:
                pass

        # Total score
        total_score = (
            (num_politicians * 3)
            + (5 if bipartisan else 0)
            + (avg_win_rate / 10)
            + recency_score
        )

        # Company name from asset_description of first trade
        company_name = ""
        for t in ticker_trades:
            desc = t.get("asset_description", "")
            if desc:
                company_name = desc
                break
        if not company_name:
            company_name = ticker

        # Price info from the most recent trade
        most_recent = max(ticker_trades, key=lambda t: t.get("tx_date", ""))
        price_at_latest = most_recent.get("price_at_trade")
        current_price = most_recent.get("current_price")

        latest_trade_date = most_recent.get("tx_date", "")

        candidates.append({
            "ticker": ticker,
            "company_name": company_name,
            "score": round(total_score, 1),
            "num_politicians": num_politicians,
            "bipartisan": bipartisan,
            "avg_win_rate": round(avg_win_rate, 1),
            "latest_trade_date": latest_trade_date,
            "price_at_latest": price_at_latest,
            "current_price": current_price,
            "politicians": politician_details,
        })

    # 5. Sort by score descending, take top 5
    candidates.sort(key=lambda c: c["score"], reverse=True)
    top_picks = candidates[:5]

    log.info("Built %d top picks from %d candidates", len(top_picks), len(candidates))
    return top_picks


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------

def run() -> None:
    """
    Full enrichment pipeline:
    1. Load trades.json
    2. Enrich with prices
    3. Write enriched trades back to trades.json
    4. Build and write summary.json
    5. Build and write latest.json
    """
    # Load trades
    if not TRADES_JSON.exists():
        log.error("trades.json not found at %s; run fetch_s3_data.py first", TRADES_JSON)
        sys.exit(1)

    try:
        with open(TRADES_JSON, "r", encoding="utf-8") as f:
            trades = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Could not load trades.json: %s", exc)
        sys.exit(1)

    log.info("Loaded %d trades from %s", len(trades), TRADES_JSON)

    # Fill in missing party data from known lookup
    PARTY_LOOKUP: dict[str, str] = {
        "A. Mitchell McConnell, Jr.": "R",
        "Angus S King, Jr.": "I",
        "Bernie Moreno": "R",
        "David H McCormick": "R",
        "Gary C Peters": "D",
        "John Boozman": "R",
        "John Fetterman": "D",
        "John W Hickenlooper": "D",
        "Katie Britt": "R",
        "Lindsey Graham": "R",
        "Mark R Warner": "D",
        "Markwayne Mullin": "R",
        "Rafael E Cruz": "R",
        "Sheldon Whitehouse": "D",
        "Shelley M Capito": "R",
        "Thomas H Tuberville": "R",
        "Tina Smith": "D",
        "Richard Blumenthal": "D",
    }
    party_filled = 0
    for t in trades:
        if not t.get("party") and t.get("politician") in PARTY_LOOKUP:
            t["party"] = PARTY_LOOKUP[t["politician"]]
            party_filled += 1
    if party_filled:
        log.info("Filled party for %d trades from lookup table", party_filled)

    # Filter out trades with empty tx_date (PDF parsing failures)
    original_count = len(trades)
    trades = [t for t in trades if t.get("tx_date", "").strip()]
    if original_count != len(trades):
        log.info("Filtered out %d trades with empty tx_date", original_count - len(trades))

    # Enrich
    trades = enrich_trades(trades)

    # Write enriched trades
    try:
        with open(TRADES_JSON, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, default=str)
        log.info("Wrote enriched trades to %s", TRADES_JSON)
    except OSError as exc:
        log.error("Could not write trades.json: %s", exc)

    # Build summary
    summary = build_summary(trades)
    try:
        with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        log.info("Wrote summary (%d politicians) to %s", len(summary), SUMMARY_JSON)
    except OSError as exc:
        log.error("Could not write summary.json: %s", exc)

    # Build latest (most recent 50 trades with tickers, sorted by date desc)
    latest = sorted(
        [t for t in trades if t.get("ticker")],
        key=lambda t: t.get("tx_date", ""),
        reverse=True,
    )[:50]
    try:
        with open(LATEST_JSON, "w", encoding="utf-8") as f:
            json.dump(latest, f, indent=2, default=str)
        log.info("Wrote %d latest trades to %s", len(latest), LATEST_JSON)
    except OSError as exc:
        log.error("Could not write latest.json: %s", exc)

    # Detect trading signals/clusters
    signals = detect_signals(trades)
    try:
        with open(SIGNALS_JSON, "w", encoding="utf-8") as f:
            json.dump(signals, f, indent=2, default=str)
        log.info("Wrote %d signals to %s", len(signals), SIGNALS_JSON)
    except OSError as exc:
        log.error("Could not write signals.json: %s", exc)

    # Build top picks
    top_picks = build_top_picks(trades, summary)
    try:
        with open(TOP_PICKS_JSON, "w", encoding="utf-8") as f:
            json.dump(top_picks, f, indent=2, default=str)
        log.info("Wrote %d top picks to %s", len(top_picks), TOP_PICKS_JSON)
    except OSError as exc:
        log.error("Could not write top_picks.json: %s", exc)

    log.info("Enrichment pipeline complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()
