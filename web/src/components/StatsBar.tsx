import { useMemo } from "react";
import type { Trade } from "@/types";
import styles from "./StatsBar.module.css";

interface StatsBarProps {
  trades: Trade[];
}

function StatsBar({ trades }: StatsBarProps) {
  const stats = useMemo(() => {
    const totalTrades = trades.length;

    // Trades this month
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const tradesThisMonth = trades.filter(
      (t) => new Date(t.tx_date) >= monthStart,
    ).length;

    // Most active politician
    const politicianCounts: Record<string, number> = {};
    for (const t of trades) {
      politicianCounts[t.politician] =
        (politicianCounts[t.politician] || 0) + 1;
    }
    let mostActivePolitician = "N/A";
    let maxPoliticianCount = 0;
    for (const [name, count] of Object.entries(politicianCounts)) {
      if (count > maxPoliticianCount) {
        maxPoliticianCount = count;
        mostActivePolitician = name;
      }
    }

    // Most traded ticker
    const tickerCounts: Record<string, number> = {};
    for (const t of trades) {
      if (t.ticker) {
        tickerCounts[t.ticker] = (tickerCounts[t.ticker] || 0) + 1;
      }
    }
    let mostTradedTicker = "N/A";
    let maxTickerCount = 0;
    for (const [ticker, count] of Object.entries(tickerCounts)) {
      if (count > maxTickerCount) {
        maxTickerCount = count;
        mostTradedTicker = ticker;
      }
    }

    return {
      totalTrades,
      tradesThisMonth,
      mostActivePolitician,
      maxPoliticianCount,
      mostTradedTicker,
      maxTickerCount,
    };
  }, [trades]);

  return (
    <div className={styles.grid}>
      <div className={styles.statCard}>
        <div className={styles.label}>Total Trades</div>
        <div className={styles.value}>{stats.totalTrades.toLocaleString()}</div>
      </div>
      <div className={styles.statCard}>
        <div className={styles.label}>This Month</div>
        <div className={styles.value}>{stats.tradesThisMonth.toLocaleString()}</div>
      </div>
      <div className={styles.statCard}>
        <div className={styles.label}>Most Active</div>
        <div className={styles.value} style={{ fontSize: "1rem" }}>
          {stats.mostActivePolitician}
        </div>
        <div className={styles.subValue}>
          {stats.maxPoliticianCount} trades
        </div>
      </div>
      <div className={styles.statCard}>
        <div className={styles.label}>Top Ticker</div>
        <div className={styles.value}>{stats.mostTradedTicker}</div>
        <div className={styles.subValue}>
          {stats.maxTickerCount} trades
        </div>
      </div>
    </div>
  );
}

export default StatsBar;
