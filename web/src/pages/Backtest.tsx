import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { useBacktest } from "@/hooks/useTradeData";
import { formatDate, formatReturn } from "@/utils/format";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { BacktestTrade } from "@/types";
import styles from "./Backtest.module.css";

type Window = "current" | "30d" | "90d";
type SortField = "ticker" | "copycat_return" | "alpha" | "timing_cost" | "days_late";
type SortDir = "asc" | "desc";

function windowLabel(w: Window): string {
  switch (w) {
    case "current": return "Hold to Now";
    case "30d": return "30 Day";
    case "90d": return "90 Day";
  }
}

function returnColor(val: number | null): string {
  if (val === null) return "var(--text-muted)";
  return val >= 0 ? "var(--green, #00c853)" : "var(--red, #ff1744)";
}

function fmtPct(val: number | null | undefined): string {
  if (val === null || val === undefined) return "N/A";
  const sign = val >= 0 ? "+" : "";
  return `${sign}${val.toFixed(1)}%`;
}

function getCopycatReturn(t: BacktestTrade, w: Window): number | null {
  switch (w) {
    case "current": return t.copycat_return_current;
    case "30d": return t.copycat_return_30d;
    case "90d": return t.copycat_return_90d;
  }
}

function getAlpha(t: BacktestTrade, w: Window): number | null {
  switch (w) {
    case "current": return t.alpha_current;
    case "30d": return t.alpha_30d;
    case "90d": return t.alpha_90d;
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className={styles.customTooltip}>
      <div className={styles.tooltipLabel}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className={styles.tooltipValue} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? fmtPct(p.value) : p.value}
        </div>
      ))}
    </div>
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function Backtest() {
  const { data, isLoading, error } = useBacktest();
  const [window, setWindow] = useState<Window>("current");
  const [showTable, setShowTable] = useState(false);
  const [sortField, setSortField] = useState<SortField>("copycat_return");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const windowKey = window === "current" ? "current" : window;

  const summary = data?.strategy_summary[windowKey];
  const bench = data?.vs_benchmark[windowKey];

  // Party chart data
  const partyData = useMemo(() => {
    if (!data?.by_party) return [];
    return Object.entries(data.by_party).map(([party, stats]) => ({
      party: party === "D" ? "Democrat" : "Republican",
      avg_return: stats.avg_return,
      win_rate: stats.win_rate,
      fill: party === "D" ? "#2196f3" : "#f44336",
    }));
  }, [data]);

  // Returns by window chart
  const windowData = useMemo(() => {
    if (!data) return [];
    return [
      {
        window: "30 Day",
        copycat: data.strategy_summary["30d"].avg_return,
        spy: data.vs_benchmark["30d"].spy_avg,
      },
      {
        window: "90 Day",
        copycat: data.strategy_summary["90d"].avg_return,
        spy: data.vs_benchmark["90d"].spy_avg,
      },
      {
        window: "Hold",
        copycat: data.strategy_summary.current.avg_return,
        spy: data.vs_benchmark.current.spy_avg,
      },
    ];
  }, [data]);

  // Year chart data
  const yearData = useMemo(() => {
    if (!data?.by_year) return [];
    return data.by_year.map((y) => ({
      year: String(y.year),
      avg_return: y.avg_return,
      win_rate: y.win_rate,
    }));
  }, [data]);

  // Delay chart data
  const delayData = useMemo(() => {
    if (!data?.by_days_late) return [];
    return data.by_days_late.map((d) => ({
      bucket: d.bucket,
      avg_return: d.avg_return,
      count: d.count,
    }));
  }, [data]);

  // Sorted individual trades
  const sortedTrades = useMemo(() => {
    if (!data?.individual_trades) return [];
    const trades = [...data.individual_trades];
    trades.sort((a, b) => {
      let aVal: number | string | null = null;
      let bVal: number | string | null = null;
      switch (sortField) {
        case "ticker": aVal = a.ticker; bVal = b.ticker; break;
        case "copycat_return": aVal = getCopycatReturn(a, window); bVal = getCopycatReturn(b, window); break;
        case "alpha": aVal = getAlpha(a, window); bVal = getAlpha(b, window); break;
        case "timing_cost": aVal = a.timing_cost; bVal = b.timing_cost; break;
        case "days_late": aVal = a.days_late; bVal = b.days_late; break;
      }
      if (aVal === null) return 1;
      if (bVal === null) return -1;
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      const diff = (aVal as number) - (bVal as number);
      return sortDir === "asc" ? diff : -diff;
    });
    return trades;
  }, [data, sortField, sortDir, window]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return "";
    return sortDir === "asc" ? " \u25B2" : " \u25BC";
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Copycat Strategy Backtest</h1>
        <p className={styles.subtitle}>
          What if you bought when politicians disclosed their trades?
        </p>
      </div>

      {isLoading && <LoadingSpinner message="Loading backtest results..." />}

      {error && (
        <div className={styles.error}>Failed to load backtest data.</div>
      )}

      {!isLoading && !error && data && data.total_trades_analyzed > 0 && (
        <>
          {/* Summary bar */}
          <div className={styles.summaryBar}>
            <div className={styles.summaryItem}>
              <span className={styles.summaryValue}>{data.total_trades_analyzed}</span>
              <span className={styles.summaryLabel}>Trades Analyzed</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryValue}>{summary?.win_rate ?? 0}%</span>
              <span className={styles.summaryLabel}>Win Rate</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryValue} style={{ color: returnColor(summary?.avg_return ?? 0) }}>
                {fmtPct(summary?.avg_return)}
              </span>
              <span className={styles.summaryLabel}>Avg Return</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryValue} style={{ color: returnColor(bench?.alpha ?? 0) }}>
                {fmtPct(bench?.alpha)}
              </span>
              <span className={styles.summaryLabel}>Alpha vs SPY</span>
            </div>
          </div>

          {/* Window toggle */}
          <div className={styles.windowToggle}>
            {(["current", "30d", "90d"] as Window[]).map((w) => (
              <button
                key={w}
                className={`${styles.windowBtn} ${window === w ? styles.windowBtnActive : ""}`}
                onClick={() => setWindow(w)}
              >
                {windowLabel(w)}
              </button>
            ))}
          </div>

          {/* Insight cards */}
          <div className={styles.insightGrid}>
            <div className={styles.insightCard}>
              <div className={styles.insightTitle}>Politician Timing Advantage</div>
              <div className={styles.insightStat}>
                <span>Avg timing cost</span>
                <span className={styles.insightStatValue}>
                  {fmtPct(data.politician_vs_copycat.avg_timing_cost)}
                </span>
              </div>
              <div className={styles.insightStat}>
                <span>Delay hurt in</span>
                <span className={styles.insightStatValue}>
                  {data.politician_vs_copycat.pct_where_delay_hurt.toFixed(0)}% of trades
                </span>
              </div>
              <div className={styles.insightStat}>
                <span>Politician avg return</span>
                <span className={styles.insightStatValue}>
                  {fmtPct(data.politician_vs_copycat.avg_politician_return)}
                </span>
              </div>
              <div className={styles.insightStat}>
                <span>Copycat avg return</span>
                <span className={styles.insightStatValue}>
                  {fmtPct(data.politician_vs_copycat.avg_copycat_return)}
                </span>
              </div>
            </div>
            <div className={styles.insightCard}>
              <div className={styles.insightTitle}>Best Holding Period</div>
              {(["30d", "90d", "current"] as Window[]).map((w) => {
                const s = data.strategy_summary[w === "current" ? "current" : w];
                return (
                  <div key={w} className={styles.insightStat}>
                    <span>{windowLabel(w)}</span>
                    <span className={styles.insightStatValue} style={{ color: returnColor(s.avg_return) }}>
                      {fmtPct(s.avg_return)} ({s.win_rate}% win)
                    </span>
                  </div>
                );
              })}
              <div className={styles.insightStat}>
                <span>Beat SPY ({windowLabel(window)})</span>
                <span className={styles.insightStatValue}>
                  {bench?.beat_spy_pct ?? 0}%
                </span>
              </div>
            </div>
          </div>

          {/* Charts */}
          <div className={styles.chartGrid}>
            {/* Win Rate by Party */}
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>Win Rate by Party</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={partyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                  <XAxis dataKey="party" stroke="#888" tick={{ fill: "#888", fontSize: 12 }} />
                  <YAxis stroke="#888" tick={{ fill: "#888", fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="win_rate" name="Win Rate" radius={[4, 4, 0, 0]}>
                    {partyData.map((entry, i) => (
                      <rect key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Returns by Holding Period */}
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>Returns by Holding Period</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={windowData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                  <XAxis dataKey="window" stroke="#888" tick={{ fill: "#888", fontSize: 12 }} />
                  <YAxis stroke="#888" tick={{ fill: "#888", fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="copycat" name="Copycat" fill="#7c4dff" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="spy" name="SPY" fill="#616161" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Returns by Year */}
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>Returns by Year</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={yearData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                  <XAxis dataKey="year" stroke="#888" tick={{ fill: "#888", fontSize: 12 }} />
                  <YAxis stroke="#888" tick={{ fill: "#888", fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="avg_return" name="Avg Return" fill="#00e676" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Impact of Disclosure Delay */}
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>Impact of Disclosure Delay</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={delayData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                  <XAxis dataKey="bucket" stroke="#888" tick={{ fill: "#888", fontSize: 12 }} />
                  <YAxis stroke="#888" tick={{ fill: "#888", fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="avg_return" name="Avg Return" fill="#ffc107" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Breakdowns */}
          <h2 className={styles.sectionTitle}>By Trade Size</h2>
          <div className={styles.breakdownGrid}>
            {Object.entries(data.by_amount).map(([size, stats]) => (
              <div key={size} className={styles.breakdownCard}>
                <div className={styles.breakdownLabel}>
                  {size === "small" ? "$1K-$15K" : size === "medium" ? "$15K-$100K" : "$100K+"}
                </div>
                <div className={styles.breakdownValue} style={{ color: returnColor(stats.avg_return) }}>
                  {fmtPct(stats.avg_return)}
                </div>
                <div className={styles.breakdownSub}>
                  {stats.count} trades | {stats.win_rate}% win rate
                </div>
              </div>
            ))}
          </div>

          <h2 className={styles.sectionTitle}>By Disclosure Delay</h2>
          <div className={styles.breakdownGrid}>
            {data.by_days_late.map((d) => (
              <div key={d.bucket} className={styles.breakdownCard}>
                <div className={styles.breakdownLabel}>{d.bucket}</div>
                <div className={styles.breakdownValue} style={{ color: returnColor(d.avg_return) }}>
                  {fmtPct(d.avg_return)}
                </div>
                <div className={styles.breakdownSub}>
                  {d.count} trades | {d.win_rate}% win rate
                </div>
              </div>
            ))}
          </div>

          {/* Top / Worst trades */}
          <div className={styles.tradesSection}>
            <h2 className={styles.sectionTitle}>Top 10 Trades</h2>
            <div className={styles.tradesList}>
              {data.top_trades.best.map((t) => {
                const ret = formatReturn(t.copycat_return_current ?? 0);
                return (
                  <Link key={t.id} to={`/trade/${t.id}`} className={styles.tradeRow}>
                    <span
                      className={styles.partyDot}
                      style={{ background: t.party === "D" ? "#2196f3" : t.party === "R" ? "#f44336" : "#888" }}
                    />
                    <span className={styles.tradeTicker}>{t.ticker}</span>
                    <span className={styles.tradePolitician}>{t.politician}</span>
                    <span className={styles.tradeReturn} style={{ color: returnColor(t.copycat_return_current ?? null) }}>
                      {ret.text}
                    </span>
                    <span className={styles.tradeAlpha}>
                      alpha {fmtPct(t.alpha_current ?? null)}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>

          <div className={styles.tradesSection}>
            <h2 className={styles.sectionTitle}>Worst 10 Trades</h2>
            <div className={styles.tradesList}>
              {data.top_trades.worst.map((t) => {
                const ret = formatReturn(t.copycat_return_current ?? 0);
                return (
                  <Link key={t.id} to={`/trade/${t.id}`} className={styles.tradeRow}>
                    <span
                      className={styles.partyDot}
                      style={{ background: t.party === "D" ? "#2196f3" : t.party === "R" ? "#f44336" : "#888" }}
                    />
                    <span className={styles.tradeTicker}>{t.ticker}</span>
                    <span className={styles.tradePolitician}>{t.politician}</span>
                    <span className={styles.tradeReturn} style={{ color: returnColor(t.copycat_return_current ?? null) }}>
                      {ret.text}
                    </span>
                    <span className={styles.tradeAlpha}>
                      alpha {fmtPct(t.alpha_current ?? null)}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Collapsible full trade table */}
          <button
            className={styles.tableToggle}
            onClick={() => setShowTable(!showTable)}
          >
            {showTable ? "\u25BC" : "\u25B6"} {showTable ? "Hide" : "Show"} All {data.total_trades_analyzed} Trades
          </button>

          {showTable && (
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th onClick={() => handleSort("ticker")}>Ticker{sortIndicator("ticker")}</th>
                    <th>Politician</th>
                    <th>Disclosed</th>
                    <th onClick={() => handleSort("days_late")}>Days Late{sortIndicator("days_late")}</th>
                    <th onClick={() => handleSort("copycat_return")}>Return{sortIndicator("copycat_return")}</th>
                    <th>SPY</th>
                    <th onClick={() => handleSort("alpha")}>Alpha{sortIndicator("alpha")}</th>
                    <th onClick={() => handleSort("timing_cost")}>Timing Cost{sortIndicator("timing_cost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedTrades.map((t) => {
                    const ret = getCopycatReturn(t, window);
                    const alpha = getAlpha(t, window);
                    const spyRet = window === "current" ? t.spy_return_current :
                                   window === "30d" ? t.spy_return_30d : t.spy_return_90d;
                    return (
                      <tr key={t.id}>
                        <td style={{ fontFamily: "var(--font-mono, monospace)", fontWeight: 700, color: "var(--accent)" }}>
                          <Link to={`/trade/${t.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                            {t.ticker}
                          </Link>
                        </td>
                        <td>{t.politician}</td>
                        <td className={styles.textMuted}>{formatDate(t.disclosure_date)}</td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)" }}>{t.days_late}</td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)", color: returnColor(ret) }}>
                          {fmtPct(ret)}
                        </td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--text-muted)" }}>
                          {fmtPct(spyRet)}
                        </td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)", color: returnColor(alpha) }}>
                          {fmtPct(alpha)}
                        </td>
                        <td style={{ fontFamily: "var(--font-mono, monospace)", color: returnColor(t.timing_cost) }}>
                          {fmtPct(t.timing_cost)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!isLoading && !error && (!data || data.total_trades_analyzed === 0) && (
        <div className={styles.empty}>
          <p>No backtest data available yet.</p>
          <p className={styles.emptyHint}>
            Backtest results will appear here once the data pipeline runs.
          </p>
        </div>
      )}
    </div>
  );
}

export default Backtest;
