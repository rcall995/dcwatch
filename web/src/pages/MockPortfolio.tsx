import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useTrades } from "@/hooks/useTradeData";
import { useMockTrades } from "@/hooks/useMockTrades";
import { formatDate } from "@/utils/format";
import styles from "./MockPortfolio.module.css";

function MockPortfolio() {
  const { data: trades } = useTrades();
  const { mockTrades, removeMockTrade, updatePrices } = useMockTrades();

  useEffect(() => {
    if (trades && trades.length > 0) {
      updatePrices(trades);
    }
  }, [trades, updatePrices]);

  const calcPnL = (entry: number, current: number, direction: "buy" | "sell") => {
    if (!entry || !current) return { dollars: 0, percent: 0 };
    const diff = direction === "buy" ? current - entry : entry - current;
    return {
      dollars: Math.round(diff * 100) / 100,
      percent: Math.round((diff / entry) * 10000) / 100,
    };
  };

  const totalPnLPercent =
    mockTrades.length > 0
      ? mockTrades.reduce((sum, m) => {
          const pnl = calcPnL(m.entry_price, m.current_price, m.tx_type);
          return sum + pnl.percent;
        }, 0) / mockTrades.length
      : 0;

  const winCount = mockTrades.filter((m) => {
    const pnl = calcPnL(m.entry_price, m.current_price, m.tx_type);
    return pnl.percent > 0;
  }).length;

  const winRate =
    mockTrades.length > 0
      ? Math.round((winCount / mockTrades.length) * 100)
      : 0;

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Mock Portfolio</h1>
      <p className={styles.subtitle}>
        Track hypothetical positions inspired by congressional trades
      </p>

      {mockTrades.length > 0 && (
        <div className={styles.statsRow}>
          <div className={styles.stat}>
            <span className={styles.statValue}>{mockTrades.length}</span>
            <span className={styles.statLabel}>Positions</span>
          </div>
          <div className={styles.stat}>
            <span
              className={styles.statValue}
              style={{ color: totalPnLPercent >= 0 ? "var(--green)" : "var(--red)" }}
            >
              {totalPnLPercent >= 0 ? "+" : ""}
              {totalPnLPercent.toFixed(1)}%
            </span>
            <span className={styles.statLabel}>Avg P&L</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{winRate}%</span>
            <span className={styles.statLabel}>Win Rate</span>
          </div>
        </div>
      )}

      {mockTrades.length === 0 && (
        <div className={styles.empty}>
          <p>No mock trades yet.</p>
          <p className={styles.emptyHint}>
            Browse <Link to="/">recent trades</Link> to start following
            congressional moves.
          </p>
        </div>
      )}

      <div className={styles.grid}>
        {mockTrades.map((mock) => {
          const pnl = calcPnL(mock.entry_price, mock.current_price, mock.tx_type);
          const isPositive = pnl.percent >= 0;

          return (
            <div key={mock.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.ticker}>{mock.ticker}</span>
                <span
                  className={styles.direction}
                  style={{
                    color: mock.tx_type === "buy" ? "var(--green)" : "var(--red)",
                  }}
                >
                  {mock.tx_type.toUpperCase()}
                </span>
              </div>
              <div className={styles.politician}>
                Inspired by {mock.politician}
              </div>
              <div className={styles.priceRow}>
                <div>
                  <span className={styles.priceLabel}>Entry</span>
                  <span className={styles.priceValue}>
                    ${mock.entry_price.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className={styles.priceLabel}>Current</span>
                  <span className={styles.priceValue}>
                    ${mock.current_price.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className={styles.priceLabel}>P&L</span>
                  <span
                    className={styles.priceValue}
                    style={{ color: isPositive ? "var(--green)" : "var(--red)" }}
                  >
                    {isPositive ? "+" : ""}
                    {pnl.percent.toFixed(1)}%
                  </span>
                </div>
              </div>
              {mock.notes && (
                <div className={styles.notes}>{mock.notes}</div>
              )}
              <div className={styles.cardFooter}>
                <span className={styles.date}>
                  Opened {formatDate(mock.created_at.split("T")[0])}
                </span>
                <button
                  className={styles.closeBtn}
                  onClick={() => removeMockTrade(mock.id)}
                >
                  Close Position
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default MockPortfolio;
