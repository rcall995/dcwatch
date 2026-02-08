import { useSignals } from "@/hooks/useTradeData";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./Signals.module.css";

function Signals() {
  const { data: signals, isLoading, error } = useSignals();

  const sorted = signals
    ? [...signals].sort((a, b) => b.heat_score - a.heat_score)
    : [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Trading Signals</h1>
        <p className={styles.subtitle}>
          Clusters where 3+ politicians traded the same stock within 10 days
        </p>
      </div>

      {isLoading && <LoadingSpinner message="Loading signals..." />}

      {error && (
        <div className={styles.error}>Failed to load signals data.</div>
      )}

      {!isLoading && !error && sorted.length === 0 && (
        <div className={styles.empty}>
          <p>No trading signals detected yet.</p>
          <p className={styles.emptyHint}>
            Signals appear when multiple politicians trade the same stock in a
            short time window.
          </p>
        </div>
      )}

      {!isLoading && !error && sorted.length > 0 && (
        <div className={styles.grid}>
          {sorted.map((signal, i) => (
            <div key={`${signal.ticker}-${i}`} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.ticker}>{signal.ticker}</span>
                <span className={styles.heatBadge}>
                  {signal.heat_score.toFixed(0)}
                </span>
              </div>
              <div className={styles.companyName}>
                {signal.company_name || signal.ticker}
              </div>
              <div className={styles.dateRange}>
                {signal.start_date} — {signal.end_date}
              </div>
              {signal.bipartisan && (
                <span className={styles.bipartisanBadge}>Bipartisan</span>
              )}
              <div className={styles.politicians}>
                {signal.politicians.map((p, j) => (
                  <div key={j} className={styles.politicianRow}>
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
                    <span className={styles.politicianName}>{p.name}</span>
                    <span className={styles.txInfo}>
                      {p.tx_type} on {p.tx_date}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Signals;
