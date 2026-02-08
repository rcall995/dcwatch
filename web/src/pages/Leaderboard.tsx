import { useState, useMemo } from "react";
import { useLeaderboard } from "@/hooks/useTradeData";
import LeaderboardTable from "@/components/LeaderboardTable";
import PartyComparison from "@/components/PartyComparison";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./Leaderboard.module.css";

function Leaderboard() {
  const { data, isLoading, error } = useLeaderboard();
  const [chamber, setChamber] = useState<"all" | "house" | "senate">("all");
  const [party, setParty] = useState<"all" | "D" | "R" | "I">("all");

  const filtered = useMemo(() => {
    if (!data) return [];
    let result = [...data];
    if (chamber !== "all") {
      result = result.filter((p) => p.chamber === chamber);
    }
    if (party !== "all") {
      result = result.filter((p) => p.party.toUpperCase() === party);
    }
    return result;
  }, [data, chamber, party]);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Leaderboard</h1>
        <div className={styles.filters}>
          <select
            className={styles.filterSelect}
            value={chamber}
            onChange={(e) =>
              setChamber(e.target.value as "all" | "house" | "senate")
            }
          >
            <option value="all">All Chambers</option>
            <option value="house">House</option>
            <option value="senate">Senate</option>
          </select>
          <select
            className={styles.filterSelect}
            value={party}
            onChange={(e) =>
              setParty(e.target.value as "all" | "D" | "R" | "I")
            }
          >
            <option value="all">All Parties</option>
            <option value="D">Democrat</option>
            <option value="R">Republican</option>
            <option value="I">Independent</option>
          </select>
        </div>
      </div>

      {isLoading && <LoadingSpinner message="Loading leaderboard..." />}

      {error && (
        <div style={{ color: "var(--red)", textAlign: "center", padding: "2rem" }}>
          Failed to load leaderboard data.
        </div>
      )}

      {!isLoading && !error && data && <PartyComparison politicians={data} />}
      {!isLoading && !error && <LeaderboardTable data={filtered} />}
    </div>
  );
}

export default Leaderboard;
