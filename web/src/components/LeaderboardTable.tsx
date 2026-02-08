import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import type { PoliticianSummary } from "@/types";
import { formatReturn } from "@/utils/format";
import styles from "./LeaderboardTable.module.css";

interface LeaderboardTableProps {
  data: PoliticianSummary[];
}

type SortField =
  | "name"
  | "party"
  | "state"
  | "chamber"
  | "total_trades"
  | "est_return_1y"
  | "win_rate";
type SortDir = "asc" | "desc";

function LeaderboardTable({ data }: LeaderboardTableProps) {
  const [sortField, setSortField] = useState<SortField>("est_return_1y");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const result = [...data];
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "party":
          cmp = a.party.localeCompare(b.party);
          break;
        case "state":
          cmp = a.state.localeCompare(b.state);
          break;
        case "chamber":
          cmp = a.chamber.localeCompare(b.chamber);
          break;
        case "total_trades":
          cmp = a.total_trades - b.total_trades;
          break;
        case "est_return_1y":
          cmp = a.est_return_1y - b.est_return_1y;
          break;
        case "win_rate":
          cmp = a.win_rate - b.win_rate;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [data, sortField, sortDir]);

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

  const nameSlug = (name: string) =>
    name.toLowerCase().replace(/\s+/g, "-");

  const getPartyBadgeClass = (p: string) => {
    switch (p.toUpperCase()) {
      case "D": return "badge-d";
      case "R": return "badge-r";
      default: return "badge-i";
    }
  };

  return (
    <div>
      {/* Desktop Table */}
      <div className={styles.desktopOnly}>
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Rank</th>
                <th onClick={() => handleSort("name")}>
                  Name
                  <span className={styles.sortIndicator}>{sortIcon("name")}</span>
                </th>
                <th onClick={() => handleSort("party")}>
                  Party
                  <span className={styles.sortIndicator}>{sortIcon("party")}</span>
                </th>
                <th onClick={() => handleSort("state")}>
                  State
                  <span className={styles.sortIndicator}>{sortIcon("state")}</span>
                </th>
                <th onClick={() => handleSort("chamber")}>
                  Chamber
                  <span className={styles.sortIndicator}>{sortIcon("chamber")}</span>
                </th>
                <th onClick={() => handleSort("total_trades")}>
                  Trades
                  <span className={styles.sortIndicator}>{sortIcon("total_trades")}</span>
                </th>
                <th onClick={() => handleSort("est_return_1y")}>
                  Est. 1Y Return
                  <span className={styles.sortIndicator}>{sortIcon("est_return_1y")}</span>
                </th>
                <th onClick={() => handleSort("win_rate")}>
                  Win Rate
                  <span className={styles.sortIndicator}>{sortIcon("win_rate")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p, idx) => {
                const returnInfo = formatReturn(p.est_return_1y);
                return (
                  <tr key={p.name} onClick={() => {}}>
                    <td className={styles.rank}>{idx + 1}</td>
                    <td>
                      <Link
                        to={`/politician/${nameSlug(p.name)}`}
                        className={styles.nameLink}
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td>
                      <span className={`${styles.partyBadge} ${getPartyBadgeClass(p.party)}`}>
                        {p.party}
                      </span>
                    </td>
                    <td>{p.state}</td>
                    <td className={styles.chamber}>
                      {p.chamber === "house" ? "House" : "Senate"}
                    </td>
                    <td>{p.total_trades}</td>
                    <td className={returnInfo.colorClass}>{returnInfo.text}</td>
                    <td>{p.win_rate.toFixed(0)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile Cards */}
      <div className={styles.mobileOnly}>
        <div className={styles.cardList}>
          {sorted.map((p, idx) => {
            const returnInfo = formatReturn(p.est_return_1y);
            return (
              <Link
                key={p.name}
                to={`/politician/${nameSlug(p.name)}`}
                className={styles.mobileCard}
              >
                <div className={styles.mobileCardHeader}>
                  <span className={styles.mobileCardName}>
                    {idx + 1}. {p.name}
                  </span>
                  <span className={`${styles.partyBadge} ${getPartyBadgeClass(p.party)}`}>
                    {p.party}
                  </span>
                </div>
                <div className={styles.mobileCardStats}>
                  <div className={styles.mobileCardStat}>
                    <span className={styles.mobileCardLabel}>Return</span>
                    <span className={`${styles.mobileCardValue} ${returnInfo.colorClass}`}>
                      {returnInfo.text}
                    </span>
                  </div>
                  <div className={styles.mobileCardStat}>
                    <span className={styles.mobileCardLabel}>Trades</span>
                    <span className={styles.mobileCardValue}>{p.total_trades}</span>
                  </div>
                  <div className={styles.mobileCardStat}>
                    <span className={styles.mobileCardLabel}>Win Rate</span>
                    <span className={styles.mobileCardValue}>
                      {p.win_rate.toFixed(0)}%
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default LeaderboardTable;
