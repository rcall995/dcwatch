import { useTopPicks } from "@/hooks/useTradeData";
import { formatDate } from "@/utils/format";
import styles from "./TopPicks.module.css";

function TopPicks() {
  const { data: picks, isLoading } = useTopPicks();

  if (isLoading || !picks || picks.length === 0) {
    return null; // Don't show section if no data
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Top Picks</h2>
      <p className={styles.subtitle}>
        Most-bought stocks by high-performing politicians in the last 60 days
      </p>
      <div className={styles.grid}>
        {picks.map((pick, i) => (
          <div key={pick.ticker} className={styles.card}>
            <div className={styles.rank}>#{i + 1}</div>
            <div className={styles.cardBody}>
              <div className={styles.cardHeader}>
                <span className={styles.ticker}>{pick.ticker}</span>
                <span className={styles.scoreBadge}>
                  {pick.score.toFixed(0)}
                </span>
              </div>
              <div className={styles.companyName}>
                {pick.company_name || pick.ticker}
              </div>
              <div className={styles.statsRow}>
                <div className={styles.statItem}>
                  <span className={styles.statValue}>{pick.num_politicians}</span>
                  <span className={styles.statLabel}>Buyers</span>
                </div>
                <div className={styles.statItem}>
                  <span className={styles.statValue}>{pick.avg_win_rate.toFixed(0)}%</span>
                  <span className={styles.statLabel}>Avg Win Rate</span>
                </div>
                {pick.current_price != null && (
                  <div className={styles.statItem}>
                    <span className={styles.statValue}>
                      ${pick.current_price.toFixed(2)}
                    </span>
                    <span className={styles.statLabel}>Price</span>
                  </div>
                )}
              </div>
              <div className={styles.badges}>
                {pick.bipartisan && (
                  <span className={styles.bipartisanBadge}>Bipartisan</span>
                )}
                <span className={styles.dateBadge}>
                  Latest: {formatDate(pick.latest_trade_date)}
                </span>
              </div>
              <div className={styles.buyerList}>
                {pick.politicians.slice(0, 3).map((p, j) => (
                  <span key={j} className={styles.buyerTag}>
                    <span
                      className={styles.partyDot}
                      style={{
                        background:
                          p.party.toUpperCase() === "D"
                            ? "var(--party-d)"
                            : p.party.toUpperCase() === "R"
                              ? "var(--party-r)"
                              : "var(--text-muted)",
                      }}
                    />
                    {p.name.split(" ").pop()}
                  </span>
                ))}
                {pick.politicians.length > 3 && (
                  <span className={styles.moreTag}>
                    +{pick.politicians.length - 3} more
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TopPicks;
