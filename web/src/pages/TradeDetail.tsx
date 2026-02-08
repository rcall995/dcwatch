import { useParams, useNavigate, Link } from "react-router-dom";
import { useTrades } from "@/hooks/useTradeData";
import {
  formatDate,
  formatAmount,
  formatReturn,
  txTypeLabel,
  txTypeColor,
} from "@/utils/format";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./TradeDetail.module.css";

function TradeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: trades, isLoading } = useTrades();

  const trade = trades?.find((t) => t.id === id);

  const nameSlug = (n: string) => n.toLowerCase().replace(/\s+/g, "-");

  const getPartyBadgeClass = (p: string) => {
    switch (p.toUpperCase()) {
      case "D": return "badge-d";
      case "R": return "badge-r";
      default: return "badge-i";
    }
  };

  if (isLoading) {
    return (
      <div className={styles.page}>
        <LoadingSpinner message="Loading trade details..." />
      </div>
    );
  }

  if (!trade) {
    return (
      <div className={styles.page}>
        <button className={styles.backButton} onClick={() => navigate(-1)}>
          {"\u2190"} Back
        </button>
        <div className={styles.empty}>Trade not found.</div>
      </div>
    );
  }

  const returnInfo = trade.est_return != null
    ? formatReturn(trade.est_return)
    : null;

  return (
    <div className={styles.page}>
      <button className={styles.backButton} onClick={() => navigate(-1)}>
        {"\u2190"} Back
      </button>

      <div className={styles.card}>
        <div className={styles.cardTitle}>
          <span className={styles.ticker}>{trade.ticker}</span>
          <span style={{ color: txTypeColor(trade.tx_type) }}>
            {txTypeLabel(trade.tx_type)}
          </span>
          {trade.is_amended && <span className={styles.amended}>Amended</span>}
        </div>

        <div className={styles.detailGrid}>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Politician</span>
            <span className={styles.detailValue}>
              <Link
                to={`/politician/${nameSlug(trade.politician)}`}
                className={styles.politicianLink}
              >
                {trade.politician}
              </Link>
              <span className={`${styles.partyBadge} ${getPartyBadgeClass(trade.party)}`}>
                {trade.party}
              </span>
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>State / Chamber</span>
            <span className={styles.detailValue}>
              {trade.state} | {trade.chamber === "house" ? "House" : "Senate"}
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Asset Description</span>
            <span className={styles.detailValue}>{trade.asset_description}</span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Asset Type</span>
            <span className={styles.detailValue} style={{ textTransform: "capitalize" }}>
              {trade.asset_type}
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Transaction Date</span>
            <span className={styles.detailValue}>{formatDate(trade.tx_date)}</span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Disclosure Date</span>
            <span className={styles.detailValue}>
              {formatDate(trade.disclosure_date)}
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Amount</span>
            <span className={styles.detailValue}>
              {formatAmount(trade.amount_low, trade.amount_high)}
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Days Late</span>
            <span
              className={styles.detailValue}
              style={{
                color: trade.days_late > 45 ? "var(--red)" : undefined,
              }}
            >
              {trade.days_late}
            </span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Owner</span>
            <span className={styles.detailValue}>{trade.owner}</span>
          </div>

          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Filing</span>
            <span className={styles.detailValue}>
              {trade.filing_url ? (
                <a
                  href={trade.filing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.filingLink}
                >
                  View Filing {"\u2197"}
                </a>
              ) : (
                "N/A"
              )}
            </span>
          </div>
        </div>

        {(trade.price_at_trade != null || trade.current_price != null || returnInfo) && (
          <div className={styles.priceSection}>
            <div className={styles.priceSectionTitle}>Price Data</div>
            <div className={styles.priceRow}>
              {trade.price_at_trade != null && (
                <div className={styles.detailItem}>
                  <span className={styles.detailLabel}>Price at Trade</span>
                  <span className={styles.detailValue}>
                    ${trade.price_at_trade.toFixed(2)}
                  </span>
                </div>
              )}
              {trade.current_price != null && (
                <div className={styles.detailItem}>
                  <span className={styles.detailLabel}>Current Price</span>
                  <span className={styles.detailValue}>
                    ${trade.current_price.toFixed(2)}
                  </span>
                </div>
              )}
              {returnInfo && (
                <div className={styles.detailItem}>
                  <span className={styles.detailLabel}>Est. Return</span>
                  <span className={`${styles.detailValue} ${returnInfo.colorClass}`}>
                    {returnInfo.text}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TradeDetail;
