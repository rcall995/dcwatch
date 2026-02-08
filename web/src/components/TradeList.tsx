import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import type { Trade } from "@/types";
import {
  formatDate,
  formatAmount,
  txTypeLabel,
  txTypeColor,
  partyColor,
} from "@/utils/format";
import styles from "./TradeList.module.css";

interface TradeListProps {
  trades: Trade[];
  showFilters?: boolean;
}

type SortField =
  | "tx_date"
  | "politician"
  | "party"
  | "ticker"
  | "tx_type"
  | "amount_low"
  | "days_late";
type SortDir = "asc" | "desc";

function TradeList({ trades, showFilters = false }: TradeListProps) {
  const [chamber, setChamber] = useState<"all" | "house" | "senate">("all");
  const [party, setParty] = useState<"all" | "D" | "R" | "I">("all");
  const [txFilter, setTxFilter] = useState<"all" | "buy" | "sell">("all");
  const [tickerFilter, setTickerFilter] = useState("");
  const [dateRange, setDateRange] = useState<"30" | "90" | "365" | "all">("all");
  const [sortField, setSortField] = useState<SortField>("tx_date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const filtered = useMemo(() => {
    let result = [...trades];

    if (showFilters) {
      if (chamber !== "all") {
        result = result.filter((t) => t.chamber === chamber);
      }
      if (party !== "all") {
        result = result.filter(
          (t) => t.party.toUpperCase() === party,
        );
      }
      if (txFilter !== "all") {
        if (txFilter === "buy") {
          result = result.filter((t) => t.tx_type === "purchase");
        } else {
          result = result.filter(
            (t) => t.tx_type === "sale_full" || t.tx_type === "sale_partial",
          );
        }
      }
      if (tickerFilter.trim()) {
        const q = tickerFilter.trim().toUpperCase();
        result = result.filter((t) => t.ticker.toUpperCase().includes(q));
      }
      if (dateRange !== "all") {
        const days = parseInt(dateRange, 10);
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        result = result.filter((t) => new Date(t.tx_date) >= cutoff);
      }
    }

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "tx_date":
          cmp = a.tx_date.localeCompare(b.tx_date);
          break;
        case "politician":
          cmp = a.politician.localeCompare(b.politician);
          break;
        case "party":
          cmp = a.party.localeCompare(b.party);
          break;
        case "ticker":
          cmp = a.ticker.localeCompare(b.ticker);
          break;
        case "tx_type":
          cmp = a.tx_type.localeCompare(b.tx_type);
          break;
        case "amount_low":
          cmp = a.amount_low - b.amount_low;
          break;
        case "days_late":
          cmp = a.days_late - b.days_late;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [trades, chamber, party, txFilter, tickerFilter, dateRange, sortField, sortDir, showFilters]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortIcon = (field: SortField) => {
    if (sortField !== field) return "";
    return sortDir === "asc" ? "\u25B2" : "\u25BC";
  };

  if (!trades || trades.length === 0) {
    return (
      <div>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={styles.skeleton} />
        ))}
      </div>
    );
  }

  const nameSlug = (name: string) =>
    name.toLowerCase().replace(/\s+/g, "-");

  const getPartyBadgeClass = (p: string) => {
    switch (p.toUpperCase()) {
      case "D": return "badge-d";
      case "R": return "badge-r";
      default: return "badge-i";
    }
  };

  const getTxBadgeClass = (type: string) => {
    if (type === "purchase") return "badge-buy";
    return "badge-sell";
  };

  return (
    <div>
      {showFilters && (
        <div className={styles.filterBar}>
          <select
            className={styles.filterSelect}
            value={chamber}
            onChange={(e) => setChamber(e.target.value as typeof chamber)}
          >
            <option value="all">All Chambers</option>
            <option value="house">House</option>
            <option value="senate">Senate</option>
          </select>
          <select
            className={styles.filterSelect}
            value={party}
            onChange={(e) => setParty(e.target.value as typeof party)}
          >
            <option value="all">All Parties</option>
            <option value="D">Democrat</option>
            <option value="R">Republican</option>
            <option value="I">Independent</option>
          </select>
          <select
            className={styles.filterSelect}
            value={txFilter}
            onChange={(e) => setTxFilter(e.target.value as typeof txFilter)}
          >
            <option value="all">All Types</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <input
            type="text"
            className={styles.filterInput}
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value)}
            placeholder="Ticker..."
          />
          <select
            className={styles.filterSelect}
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as typeof dateRange)}
          >
            <option value="all">All Time</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
            <option value="365">Last 1 Year</option>
          </select>
        </div>
      )}

      {filtered.length === 0 && (
        <div className={styles.empty}>No trades match the current filters.</div>
      )}

      {/* Desktop Table */}
      {filtered.length > 0 && (
        <div className={styles.desktopOnly}>
          <div className={styles.tableContainer}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th onClick={() => handleSort("tx_date")}>
                    Date
                    <span className={styles.sortIndicator}>{sortIcon("tx_date")}</span>
                  </th>
                  <th onClick={() => handleSort("politician")}>
                    Politician
                    <span className={styles.sortIndicator}>{sortIcon("politician")}</span>
                  </th>
                  <th onClick={() => handleSort("party")}>
                    Party
                    <span className={styles.sortIndicator}>{sortIcon("party")}</span>
                  </th>
                  <th onClick={() => handleSort("ticker")}>
                    Ticker
                    <span className={styles.sortIndicator}>{sortIcon("ticker")}</span>
                  </th>
                  <th onClick={() => handleSort("tx_type")}>
                    Type
                    <span className={styles.sortIndicator}>{sortIcon("tx_type")}</span>
                  </th>
                  <th onClick={() => handleSort("amount_low")}>
                    Amount
                    <span className={styles.sortIndicator}>{sortIcon("amount_low")}</span>
                  </th>
                  <th onClick={() => handleSort("days_late")}>
                    Days Late
                    <span className={styles.sortIndicator}>{sortIcon("days_late")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade) => (
                  <tr key={trade.id}>
                    <td>{formatDate(trade.tx_date)}</td>
                    <td>
                      <Link
                        to={`/politician/${nameSlug(trade.politician)}`}
                        className={styles.politicianLink}
                      >
                        {trade.politician}
                      </Link>
                    </td>
                    <td>
                      <span className={`${styles.partyBadge} ${getPartyBadgeClass(trade.party)}`}>
                        {trade.party}
                      </span>
                    </td>
                    <td>
                      <Link to={`/trade/${trade.id}`} className={styles.ticker}>
                        {trade.ticker}
                      </Link>
                    </td>
                    <td>
                      <span
                        className={`${styles.txBadge} ${getTxBadgeClass(trade.tx_type)}`}
                        style={{ color: txTypeColor(trade.tx_type) }}
                      >
                        {txTypeLabel(trade.tx_type)}
                      </span>
                    </td>
                    <td>{formatAmount(trade.amount_low, trade.amount_high)}</td>
                    <td>
                      <span
                        className={`${styles.daysLate} ${trade.days_late > 45 ? styles.daysLateWarn : ""}`}
                      >
                        {trade.days_late}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Mobile Cards */}
      {filtered.length > 0 && (
        <div className={styles.mobileOnly}>
          <div className={styles.cardList}>
            {filtered.map((trade) => (
              <div key={trade.id} className={styles.tradeCard}>
                <div className={styles.cardRow}>
                  <Link
                    to={`/politician/${nameSlug(trade.politician)}`}
                    className={styles.politicianLink}
                  >
                    {trade.politician}
                  </Link>
                  <span className={`${styles.partyBadge} ${getPartyBadgeClass(trade.party)}`}>
                    {trade.party}
                  </span>
                </div>
                <div className={styles.cardRow}>
                  <Link to={`/trade/${trade.id}`} className={styles.ticker}>
                    {trade.ticker}
                  </Link>
                  <span
                    className={`${styles.txBadge} ${getTxBadgeClass(trade.tx_type)}`}
                    style={{ color: txTypeColor(trade.tx_type) }}
                  >
                    {txTypeLabel(trade.tx_type)}
                  </span>
                </div>
                <div className={styles.cardRow}>
                  <span className={styles.cardDate}>{formatDate(trade.tx_date)}</span>
                  <span className={styles.cardAmount}>
                    {formatAmount(trade.amount_low, trade.amount_high)}
                  </span>
                </div>
                {trade.days_late > 0 && (
                  <div className={styles.cardRow}>
                    <span
                      className={`${styles.daysLate} ${trade.days_late > 45 ? styles.daysLateWarn : ""}`}
                    >
                      {trade.days_late} days late
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default TradeList;
