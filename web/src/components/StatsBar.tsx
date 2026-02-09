import { useMemo } from "react";
import type { Trade, PoliticianSummary } from "@/types";
import styles from "./StatsBar.module.css";

interface StatsBarProps {
  trades: Trade[];
  summary?: PoliticianSummary[];
}

function StatsBar({ trades, summary }: StatsBarProps) {
  const stats = useMemo(() => {
    // Use summary for accurate totals when available
    const totalTrades = summary
      ? summary.reduce((sum, p) => sum + p.total_trades, 0)
      : trades.length;

    const totalPoliticians = summary ? summary.length : 0;

    // Most active politician (from summary if available)
    let mostActivePolitician = "N/A";
    let maxPoliticianCount = 0;
    if (summary && summary.length > 0) {
      for (const p of summary) {
        if (p.total_trades > maxPoliticianCount) {
          maxPoliticianCount = p.total_trades;
          mostActivePolitician = p.name;
        }
      }
    } else {
      const politicianCounts: Record<string, number> = {};
      for (const t of trades) {
        politicianCounts[t.politician] =
          (politicianCounts[t.politician] || 0) + 1;
      }
      for (const [name, count] of Object.entries(politicianCounts)) {
        if (count > maxPoliticianCount) {
          maxPoliticianCount = count;
          mostActivePolitician = name;
        }
      }
    }

    // Top performer by return (from summary)
    let topPerformer = "N/A";
    let topReturn = 0;
    if (summary && summary.length > 0) {
      for (const p of summary) {
        if (p.total_trades >= 3 && p.est_return_1y > topReturn) {
          topReturn = p.est_return_1y;
          topPerformer = p.name;
        }
      }
    }

    return {
      totalTrades,
      totalPoliticians,
      mostActivePolitician,
      maxPoliticianCount,
      topPerformer,
      topReturn,
    };
  }, [trades, summary]);

  return (
    <div className={styles.grid}>
      <div className={styles.statCard}>
        <div className={styles.label}>Total Trades</div>
        <div className={styles.value}>{stats.totalTrades.toLocaleString()}</div>
      </div>
      <div className={styles.statCard}>
        <div className={styles.label}>Politicians Tracked</div>
        <div className={styles.value}>{stats.totalPoliticians.toLocaleString()}</div>
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
        <div className={styles.label}>Top Performer</div>
        <div className={styles.value} style={{ fontSize: "1rem" }}>
          {stats.topPerformer}
        </div>
        {stats.topReturn !== 0 && (
          <div className={styles.subValue} style={{ color: stats.topReturn > 0 ? "var(--green)" : "var(--red)" }}>
            {stats.topReturn > 0 ? "+" : ""}{stats.topReturn.toFixed(1)}% avg return
          </div>
        )}
      </div>
    </div>
  );
}

export default StatsBar;
