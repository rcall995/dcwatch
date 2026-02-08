import { Link } from "react-router-dom";
import type { PoliticianSummary } from "@/types";
import { formatReturn, partyColor } from "@/utils/format";
import styles from "./PoliticianCard.module.css";

interface PoliticianCardProps {
  politician: PoliticianSummary;
}

function PoliticianCard({ politician }: PoliticianCardProps) {
  const returnInfo = formatReturn(politician.est_return_1y);
  const nameSlug = politician.name.toLowerCase().replace(/\s+/g, "-");

  const badgeClass = politician.party.toUpperCase() === "D"
    ? "badge-d"
    : politician.party.toUpperCase() === "R"
      ? "badge-r"
      : "badge-i";

  return (
    <Link to={`/politician/${nameSlug}`} className={styles.card}>
      <div className={styles.header}>
        <span className={styles.name}>{politician.name}</span>
        <span
          className={`${styles.partyBadge} ${badgeClass}`}
          style={{ backgroundColor: undefined }}
        >
          <span className={badgeClass}>{politician.party}</span>
        </span>
        <span className={styles.meta}>
          {politician.state} | {politician.chamber === "house" ? "House" : "Senate"}
        </span>
      </div>

      <div className={styles.statsRow}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Trades</span>
          <span className={styles.statValue}>{politician.total_trades}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Est. Return</span>
          <span
            className={`${styles.statValue} ${returnInfo.colorClass}`}
          >
            {returnInfo.text}
          </span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Win Rate</span>
          <span className={styles.statValue}>
            {politician.win_rate.toFixed(0)}%
          </span>
        </div>
      </div>

      {(politician.best_trade || politician.worst_trade) && (
        <div className={styles.trades}>
          {politician.best_trade && (
            <div>
              <span className={styles.tradeLabel}>Best: </span>
              <span className={styles.ticker}>{politician.best_trade.ticker}</span>
              {" "}
              <span style={{ color: partyColor("") }}>
                <span className="text-green">
                  {formatReturn(politician.best_trade.est_return).text}
                </span>
              </span>
            </div>
          )}
          {politician.worst_trade && (
            <div>
              <span className={styles.tradeLabel}>Worst: </span>
              <span className={styles.ticker}>{politician.worst_trade.ticker}</span>
              {" "}
              <span className="text-red">
                {formatReturn(politician.worst_trade.est_return).text}
              </span>
            </div>
          )}
        </div>
      )}
    </Link>
  );
}

export default PoliticianCard;
