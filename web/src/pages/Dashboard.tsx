import { useLatestTrades } from "@/hooks/useTradeData";
import ThemeToggle from "@/components/ThemeToggle";
import StatsBar from "@/components/StatsBar";
import TradeList from "@/components/TradeList";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./Dashboard.module.css";

function Dashboard() {
  const { data: trades, isLoading, error, refetch } = useLatestTrades();

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>DC</span> Watcher
        </h1>
        <ThemeToggle />
      </div>

      {isLoading && <LoadingSpinner message="Loading latest trades..." />}

      {error && (
        <div className={styles.errorBox}>
          <p>Failed to load trade data.</p>
          <p>{(error as Error).message}</p>
          <button className={styles.retryButton} onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {trades && !isLoading && !error && (
        <>
          <StatsBar trades={trades} />

          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>Recent Trades</h2>
            <TradeList trades={trades.slice(0, 50)} showFilters={false} />
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;
