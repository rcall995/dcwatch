"""
DC-Watcher: Copycat Strategy Backtest.

Analyzes what would happen if a retail investor bought the same stocks
as politicians when disclosures became public, vs buying at trade time.

Fetches price_at_disclosure and future prices via yfinance, computes
per-trade and aggregate returns, and compares against SPY benchmark.

Output: data/backtest_results.json
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from config import BACKTEST_JSON, TRADES_JSON
from enrich import fetch_price_on_date, _load_price_cache, _save_price_cache

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("backtest")

# Rate-limit between yfinance batch calls
YF_DELAY = 0.3

BENCHMARK_TICKER = "SPY"


# ---------------------------------------------------------------------------
# Batch price fetching
# ---------------------------------------------------------------------------

def fetch_prices_for_dates(ticker: str, dates: list[str]) -> dict[str, float | None]:
    """
    Fetch closing prices for a ticker on multiple dates efficiently.
    Downloads one yfinance range covering all dates, then caches each.
    Returns dict mapping date strings to prices (or None if unavailable).
    """
    if not dates or not ticker:
        return {}

    cache = _load_price_cache(ticker)
    results: dict[str, float | None] = {}
    uncached: list[str] = []

    # Check cache first
    for d in dates:
        if d in cache:
            results[d] = cache[d]
        else:
            uncached.append(d)

    if not uncached:
        return results

    if yf is None:
        log.debug("yfinance not installed; skipping batch fetch for %s", ticker)
        for d in uncached:
            results[d] = None
        return results

    # Parse dates and find range
    parsed_dates = []
    for d in uncached:
        try:
            parsed_dates.append(date.fromisoformat(d))
        except ValueError:
            results[d] = None

    if not parsed_dates:
        return results

    min_date = min(parsed_dates) - timedelta(days=5)
    max_date = max(parsed_dates) + timedelta(days=5)

    # Don't fetch future data
    today = date.today()
    if max_date > today:
        max_date = today + timedelta(days=1)

    try:
        time.sleep(YF_DELAY)
        data = yf.download(
            ticker,
            start=min_date.isoformat(),
            end=max_date.isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        log.warning("yfinance batch error for %s: %s", ticker, exc)
        for d in uncached:
            if d not in results:
                results[d] = None
        return results

    if data is None or data.empty:
        log.debug("No price data for %s in range %s to %s", ticker, min_date, max_date)
        for d in uncached:
            if d not in results:
                results[d] = None
        return results

    # Extract close prices - handle multi-level columns
    close_col = None
    if "Close" in data.columns:
        close_col = "Close"
    else:
        for col in data.columns:
            col_str = str(col).lower()
            if "close" in col_str:
                close_col = col
                break

    if close_col is None:
        for d in uncached:
            if d not in results:
                results[d] = None
        return results

    close_data = data[close_col].dropna()

    # Flatten to Series if DataFrame
    if hasattr(close_data, "columns"):
        close_data = close_data.squeeze()

    # Handle scalar (single value) case
    import numpy as np
    if isinstance(close_data, (float, int, np.floating, np.integer)):
        # Single value - try to get its date from the index
        for d in uncached:
            if d not in results:
                results[d] = round(float(close_data), 2)
                cache[d] = round(float(close_data), 2)
        _save_price_cache(ticker, cache)
        return results

    if hasattr(close_data, "empty") and close_data.empty:
        for d in uncached:
            if d not in results:
                results[d] = None
        return results

    # Build price map from downloaded data
    price_map: dict[str, float] = {}
    for i in range(len(close_data)):
        idx = close_data.index[i]
        idx_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        val = close_data.iloc[i]
        price_map[idx_date] = float(val.iloc[0]) if hasattr(val, "iloc") else float(val)

    # For each uncached date, find closest price
    updated_cache = False
    for d in uncached:
        if d in results:
            continue

        price = None
        if d in price_map:
            price = price_map[d]
        else:
            # Take closest date <= target
            earlier = {pd: p for pd, p in price_map.items() if pd <= d}
            if earlier:
                price = earlier[max(earlier)]
            elif price_map:
                # Take earliest available
                later = {pd: p for pd, p in price_map.items() if pd > d}
                if later:
                    price = later[min(later)]

        if price is not None:
            price = round(price, 2)
            cache[d] = price
            updated_cache = True

        results[d] = price

    if updated_cache:
        _save_price_cache(ticker, cache)

    return results


# ---------------------------------------------------------------------------
# Return calculations
# ---------------------------------------------------------------------------

def calc_return(buy_price: float | None, sell_price: float | None) -> float | None:
    """Calculate percentage return. Returns None if prices unavailable."""
    if buy_price and sell_price and buy_price > 0:
        return round((sell_price - buy_price) / buy_price * 100, 2)
    return None


def amount_bucket(amount_low: int, amount_high: int) -> str:
    """Categorize trade by amount size."""
    mid = (amount_low + amount_high) / 2
    if mid <= 15000:
        return "small"
    elif mid <= 100000:
        return "medium"
    else:
        return "large"


def days_late_bucket(days: int) -> str:
    """Categorize disclosure delay."""
    if days <= 15:
        return "0-15d"
    elif days <= 30:
        return "16-30d"
    elif days <= 45:
        return "31-45d"
    else:
        return "45d+"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def window_stats(returns: list[float]) -> dict[str, Any]:
    """Compute summary stats for a list of returns."""
    if not returns:
        return {
            "count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "median_return": 0.0,
        }
    wins = [r for r in returns if r > 0]
    return {
        "count": len(returns),
        "win_rate": round(len(wins) / len(returns) * 100, 1),
        "avg_return": round(statistics.mean(returns), 2),
        "median_return": round(statistics.median(returns), 2),
    }


def benchmark_comparison(
    copycat_returns: list[float],
    spy_returns: list[float],
) -> dict[str, Any]:
    """Compare copycat vs SPY returns."""
    if not copycat_returns or not spy_returns:
        return {
            "copycat_avg": 0.0,
            "spy_avg": 0.0,
            "alpha": 0.0,
            "beat_spy_pct": 0.0,
        }

    copycat_avg = statistics.mean(copycat_returns)
    spy_avg = statistics.mean(spy_returns)

    # Count trades where copycat beat SPY
    beat_count = 0
    paired = min(len(copycat_returns), len(spy_returns))
    for i in range(paired):
        if copycat_returns[i] > spy_returns[i]:
            beat_count += 1

    return {
        "copycat_avg": round(copycat_avg, 2),
        "spy_avg": round(spy_avg, 2),
        "alpha": round(copycat_avg - spy_avg, 2),
        "beat_spy_pct": round(beat_count / paired * 100, 1) if paired > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Main backtest pipeline
# ---------------------------------------------------------------------------

def run_backtest() -> None:
    """Run the copycat strategy backtest."""

    # Load trades
    if not TRADES_JSON.exists():
        log.error("trades.json not found at %s", TRADES_JSON)
        sys.exit(1)

    with open(TRADES_JSON, "r", encoding="utf-8") as f:
        trades = json.load(f)

    log.info("Loaded %d trades", len(trades))

    # Estimate disclosure_date where missing: tx_date + days_late, or tx_date + 30 days
    estimated_count = 0
    for t in trades:
        if not t.get("disclosure_date") and t.get("tx_date"):
            try:
                tx_dt = date.fromisoformat(t["tx_date"])
                delay = t.get("days_late", 0)
                if delay and delay > 0:
                    disc_dt = tx_dt + timedelta(days=delay + 45)
                else:
                    disc_dt = tx_dt + timedelta(days=30)  # median reporting delay
                t["disclosure_date"] = disc_dt.isoformat()
                t["disclosure_date_estimated"] = True
                estimated_count += 1
            except ValueError:
                pass

    if estimated_count:
        log.info("Estimated disclosure_date for %d trades (tx_date + 30d default)", estimated_count)

    # Filter to purchases with required fields
    eligible = [
        t for t in trades
        if t.get("tx_type") == "purchase"
        and t.get("price_at_trade")
        and t.get("disclosure_date")
        and t.get("ticker")
        and len(t.get("ticker", "")) <= 6
        and t.get("tx_date")
    ]

    log.info("Eligible trades (purchases with price_at_trade & disclosure_date): %d", len(eligible))

    if not eligible:
        log.warning("No eligible trades for backtest")
        _write_empty_results()
        return

    today = date.today()

    # Group by ticker for batch fetching
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for t in eligible:
        by_ticker[t["ticker"]].append(t)

    # Collect all dates needed per ticker
    ticker_dates: dict[str, set[str]] = defaultdict(set)
    spy_dates: set[str] = set()

    for t in eligible:
        disclosure_date = t["disclosure_date"]
        ticker = t["ticker"]
        ticker_dates[ticker].add(disclosure_date)
        spy_dates.add(disclosure_date)
        spy_dates.add(t["tx_date"])

        # Add future dates
        try:
            dd = date.fromisoformat(disclosure_date)
            d30 = dd + timedelta(days=30)
            d90 = dd + timedelta(days=90)
            if d30 <= today:
                d30_str = d30.isoformat()
                ticker_dates[ticker].add(d30_str)
                spy_dates.add(d30_str)
            if d90 <= today:
                d90_str = d90.isoformat()
                ticker_dates[ticker].add(d90_str)
                spy_dates.add(d90_str)
        except ValueError:
            pass

    # Batch fetch prices per ticker
    log.info("Fetching prices for %d tickers...", len(ticker_dates))
    ticker_prices: dict[str, dict[str, float | None]] = {}
    for i, (ticker, dates) in enumerate(sorted(ticker_dates.items())):
        if i % 50 == 0 and i > 0:
            log.info("  Fetched %d / %d tickers", i, len(ticker_dates))
        ticker_prices[ticker] = fetch_prices_for_dates(ticker, sorted(dates))

    # Fetch SPY prices
    log.info("Fetching SPY benchmark prices for %d dates...", len(spy_dates))
    spy_prices = fetch_prices_for_dates(BENCHMARK_TICKER, sorted(spy_dates))

    # Also need current prices for hold-to-now calculation
    # Use today's date for current reference
    today_str = today.isoformat()
    all_tickers_for_current = set(ticker_dates.keys()) | {BENCHMARK_TICKER}
    log.info("Fetching current prices for %d tickers...", len(all_tickers_for_current))
    current_prices: dict[str, float | None] = {}
    for ticker in sorted(all_tickers_for_current):
        prices = fetch_prices_for_dates(ticker, [today_str])
        current_prices[ticker] = prices.get(today_str)

    # Process each trade
    log.info("Computing per-trade results...")
    results: list[dict[str, Any]] = []

    # Track returns for aggregation - paired lists to maintain correspondence
    copycat_current: list[float] = []
    spy_current: list[float] = []
    copycat_30d: list[float] = []
    spy_30d: list[float] = []
    copycat_90d: list[float] = []
    spy_90d: list[float] = []

    for t in eligible:
        ticker = t["ticker"]
        disclosure_date = t["disclosure_date"]
        tx_date = t["tx_date"]
        price_at_trade = t["price_at_trade"]

        prices = ticker_prices.get(ticker, {})
        price_at_disclosure = prices.get(disclosure_date)
        curr_price = current_prices.get(ticker) or t.get("current_price")

        # Future prices
        price_30d = None
        price_90d = None
        spy_at_disclosure = spy_prices.get(disclosure_date)
        spy_at_trade = spy_prices.get(tx_date)
        spy_curr = current_prices.get(BENCHMARK_TICKER)
        spy_30d_price = None
        spy_90d_price = None

        try:
            dd = date.fromisoformat(disclosure_date)
            d30 = dd + timedelta(days=30)
            d90 = dd + timedelta(days=90)
            if d30 <= today:
                price_30d = prices.get(d30.isoformat())
                spy_30d_price = spy_prices.get(d30.isoformat())
            if d90 <= today:
                price_90d = prices.get(d90.isoformat())
                spy_90d_price = spy_prices.get(d90.isoformat())
        except ValueError:
            pass

        # Calculate returns
        politician_return = t.get("est_return")
        copycat_return_current = calc_return(price_at_disclosure, curr_price)
        copycat_return_30d = calc_return(price_at_disclosure, price_30d)
        copycat_return_90d = calc_return(price_at_disclosure, price_90d)

        # SPY returns (same windows, starting from disclosure date)
        spy_return_current = calc_return(spy_at_disclosure, spy_curr)
        spy_return_30d = calc_return(spy_at_disclosure, spy_30d_price)
        spy_return_90d = calc_return(spy_at_disclosure, spy_90d_price)

        # Alpha
        alpha_current = None
        alpha_30d = None
        alpha_90d = None
        if copycat_return_current is not None and spy_return_current is not None:
            alpha_current = round(copycat_return_current - spy_return_current, 2)
        if copycat_return_30d is not None and spy_return_30d is not None:
            alpha_30d = round(copycat_return_30d - spy_return_30d, 2)
        if copycat_return_90d is not None and spy_return_90d is not None:
            alpha_90d = round(copycat_return_90d - spy_return_90d, 2)

        # Timing cost
        timing_cost = calc_return(price_at_trade, price_at_disclosure)

        result: dict[str, Any] = {
            "id": t.get("id", ""),
            "politician": t.get("politician", ""),
            "party": t.get("party", ""),
            "ticker": ticker,
            "asset_description": t.get("asset_description", ""),
            "tx_date": tx_date,
            "disclosure_date": disclosure_date,
            "days_late": t.get("days_late") or max(0, (date.fromisoformat(disclosure_date) - date.fromisoformat(tx_date)).days),
            "amount_low": t.get("amount_low", 0),
            "amount_high": t.get("amount_high", 0),
            "price_at_trade": price_at_trade,
            "price_at_disclosure": price_at_disclosure,
            "price_30d": price_30d,
            "price_90d": price_90d,
            "current_price": curr_price,
            "politician_return": politician_return,
            "copycat_return_current": copycat_return_current,
            "copycat_return_30d": copycat_return_30d,
            "copycat_return_90d": copycat_return_90d,
            "spy_return_current": spy_return_current,
            "spy_return_30d": spy_return_30d,
            "spy_return_90d": spy_return_90d,
            "alpha_current": alpha_current,
            "alpha_30d": alpha_30d,
            "alpha_90d": alpha_90d,
            "timing_cost": timing_cost,
        }
        results.append(result)

        # Track for aggregation (only when both sides have data)
        if copycat_return_current is not None and spy_return_current is not None:
            copycat_current.append(copycat_return_current)
            spy_current.append(spy_return_current)
        if copycat_return_30d is not None and spy_return_30d is not None:
            copycat_30d.append(copycat_return_30d)
            spy_30d.append(spy_return_30d)
        if copycat_return_90d is not None and spy_return_90d is not None:
            copycat_90d.append(copycat_return_90d)
            spy_90d.append(spy_return_90d)

    log.info("Computed results for %d trades", len(results))

    # ── Build aggregations ──────────────────────────────────────

    # Strategy summary
    all_copycat_current = [r["copycat_return_current"] for r in results if r["copycat_return_current"] is not None]
    all_copycat_30d = [r["copycat_return_30d"] for r in results if r["copycat_return_30d"] is not None]
    all_copycat_90d = [r["copycat_return_90d"] for r in results if r["copycat_return_90d"] is not None]

    strategy_summary = {
        "current": window_stats(all_copycat_current),
        "30d": window_stats(all_copycat_30d),
        "90d": window_stats(all_copycat_90d),
    }

    # Vs benchmark
    vs_benchmark = {
        "current": benchmark_comparison(copycat_current, spy_current),
        "30d": benchmark_comparison(copycat_30d, spy_30d),
        "90d": benchmark_comparison(copycat_90d, spy_90d),
    }

    # Politician vs copycat timing analysis
    timing_costs = [r["timing_cost"] for r in results if r["timing_cost"] is not None]
    politician_returns = [r["politician_return"] for r in results if r["politician_return"] is not None]
    delay_hurt_count = len([tc for tc in timing_costs if tc > 0])

    politician_vs_copycat = {
        "avg_politician_return": round(statistics.mean(politician_returns), 2) if politician_returns else 0.0,
        "avg_copycat_return": round(statistics.mean(all_copycat_current), 2) if all_copycat_current else 0.0,
        "avg_timing_cost": round(statistics.mean(timing_costs), 2) if timing_costs else 0.0,
        "pct_where_delay_hurt": round(delay_hurt_count / len(timing_costs) * 100, 1) if timing_costs else 0.0,
    }

    # By party
    by_party: dict[str, list[float]] = defaultdict(list)
    for r in results:
        party = r.get("party", "")
        if party and r["copycat_return_current"] is not None:
            key = party[0].upper()  # D or R
            if key in ("D", "R"):
                by_party[key].append(r["copycat_return_current"])

    party_breakdown = {}
    for party_key in ("D", "R"):
        rets = by_party.get(party_key, [])
        party_breakdown[party_key] = window_stats(rets)

    # By amount
    by_amount: dict[str, list[float]] = defaultdict(list)
    for r in results:
        if r["copycat_return_current"] is not None:
            bucket = amount_bucket(r.get("amount_low", 0), r.get("amount_high", 0))
            by_amount[bucket].append(r["copycat_return_current"])

    amount_breakdown = {}
    for bucket in ("small", "medium", "large"):
        rets = by_amount.get(bucket, [])
        amount_breakdown[bucket] = window_stats(rets)

    # By year
    by_year: dict[int, list[float]] = defaultdict(list)
    for r in results:
        if r["copycat_return_current"] is not None:
            try:
                year = int(r["disclosure_date"][:4])
                by_year[year].append(r["copycat_return_current"])
            except (ValueError, IndexError):
                pass

    year_breakdown = []
    for year in sorted(by_year.keys()):
        stats = window_stats(by_year[year])
        stats["year"] = year
        year_breakdown.append(stats)

    # By days late
    by_delay: dict[str, list[float]] = defaultdict(list)
    for r in results:
        if r["copycat_return_current"] is not None:
            bucket = days_late_bucket(r.get("days_late", 0))
            by_delay[bucket].append(r["copycat_return_current"])

    delay_breakdown = []
    for bucket in ("0-15d", "16-30d", "31-45d", "45d+"):
        stats = window_stats(by_delay.get(bucket, []))
        stats["bucket"] = bucket
        delay_breakdown.append(stats)

    # Top / worst trades (by current return)
    sorted_by_current = sorted(
        [r for r in results if r["copycat_return_current"] is not None],
        key=lambda r: r["copycat_return_current"],  # type: ignore[arg-type]
        reverse=True,
    )

    top_fields = [
        "id", "politician", "party", "ticker", "tx_date", "disclosure_date",
        "days_late", "price_at_trade", "price_at_disclosure", "current_price",
        "copycat_return_current", "spy_return_current", "alpha_current", "timing_cost",
    ]

    best_trades = [
        {k: t[k] for k in top_fields if k in t}
        for t in sorted_by_current[:10]
    ]
    worst_trades = [
        {k: t[k] for k in top_fields if k in t}
        for t in sorted_by_current[-10:]
    ]

    # ── Build final output ──────────────────────────────────────

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_trades_analyzed": len(results),
        "strategy_summary": strategy_summary,
        "vs_benchmark": vs_benchmark,
        "politician_vs_copycat": politician_vs_copycat,
        "by_party": party_breakdown,
        "by_amount": amount_breakdown,
        "by_year": year_breakdown,
        "by_days_late": delay_breakdown,
        "top_trades": {
            "best": best_trades,
            "worst": worst_trades,
        },
        "individual_trades": results,
    }

    # Write output
    try:
        with open(BACKTEST_JSON, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
        log.info("Wrote backtest results to %s", BACKTEST_JSON)
    except OSError as exc:
        log.error("Could not write backtest results: %s", exc)
        sys.exit(1)

    # Print summary
    log.info("=== Backtest Summary ===")
    log.info("Trades analyzed: %d", len(results))
    if all_copycat_current:
        log.info("Copycat win rate (hold): %.1f%%", strategy_summary["current"]["win_rate"])
        log.info("Copycat avg return (hold): %.2f%%", strategy_summary["current"]["avg_return"])
        log.info("SPY avg return: %.2f%%", vs_benchmark["current"]["spy_avg"])
        log.info("Alpha vs SPY: %.2f%%", vs_benchmark["current"]["alpha"])
    if timing_costs:
        log.info("Avg timing cost: %.2f%%", politician_vs_copycat["avg_timing_cost"])
        log.info("Delay hurt in %.1f%% of trades", politician_vs_copycat["pct_where_delay_hurt"])


def _write_empty_results() -> None:
    """Write an empty results file when no eligible trades exist."""
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_trades_analyzed": 0,
        "strategy_summary": {"current": window_stats([]), "30d": window_stats([]), "90d": window_stats([])},
        "vs_benchmark": {"current": benchmark_comparison([], []), "30d": benchmark_comparison([], []), "90d": benchmark_comparison([], [])},
        "politician_vs_copycat": {"avg_politician_return": 0, "avg_copycat_return": 0, "avg_timing_cost": 0, "pct_where_delay_hurt": 0},
        "by_party": {},
        "by_amount": {},
        "by_year": [],
        "by_days_late": [],
        "top_trades": {"best": [], "worst": []},
        "individual_trades": [],
    }
    with open(BACKTEST_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    log.info("Wrote empty backtest results to %s", BACKTEST_JSON)


if __name__ == "__main__":
    run_backtest()
