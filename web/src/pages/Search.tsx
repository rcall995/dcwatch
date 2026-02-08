import { useState, useMemo, useCallback } from "react";
import { useTrades, useLeaderboard } from "@/hooks/useTradeData";
import SearchBar from "@/components/SearchBar";
import PoliticianCard from "@/components/PoliticianCard";
import TradeList from "@/components/TradeList";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./Search.module.css";

const RESULTS_LIMIT = 20;

function Search() {
  const [query, setQuery] = useState("");
  const [showAllPoliticians, setShowAllPoliticians] = useState(false);
  const [showAllTrades, setShowAllTrades] = useState(false);

  const { data: trades, isLoading: tradesLoading } = useTrades();
  const { data: leaderboard, isLoading: leaderboardLoading } = useLeaderboard();

  const isLoading = tradesLoading || leaderboardLoading;

  const handleSearch = useCallback((q: string) => {
    setQuery(q);
    setShowAllPoliticians(false);
    setShowAllTrades(false);
  }, []);

  const matchedPoliticians = useMemo(() => {
    if (!query || !leaderboard) return [];
    const lower = query.toLowerCase();
    return leaderboard.filter(
      (p) => p.name.toLowerCase().includes(lower),
    );
  }, [query, leaderboard]);

  const matchedTrades = useMemo(() => {
    if (!query || !trades) return [];
    const lower = query.toLowerCase();
    return trades.filter(
      (t) =>
        t.ticker.toLowerCase().includes(lower) ||
        t.politician.toLowerCase().includes(lower) ||
        t.asset_description.toLowerCase().includes(lower),
    );
  }, [query, trades]);

  const politiciansToShow = showAllPoliticians
    ? matchedPoliticians
    : matchedPoliticians.slice(0, RESULTS_LIMIT);

  const tradesToShow = showAllTrades
    ? matchedTrades
    : matchedTrades.slice(0, RESULTS_LIMIT);

  const hasResults = matchedPoliticians.length > 0 || matchedTrades.length > 0;

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Search</h1>

      <div className={styles.searchWrapper}>
        <SearchBar
          onSearch={handleSearch}
          placeholder="Search for a politician or ticker..."
        />
      </div>

      {isLoading && <LoadingSpinner message="Loading data..." />}

      {!isLoading && !query && (
        <div className={styles.placeholder}>
          Search for a politician or ticker symbol to see their trading activity.
        </div>
      )}

      {!isLoading && query && !hasResults && (
        <div className={styles.noResults}>
          No results found for &quot;{query}&quot;.
        </div>
      )}

      {!isLoading && query && matchedPoliticians.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Politicians</h2>
            <span className={styles.resultCount}>
              {matchedPoliticians.length} result{matchedPoliticians.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className={styles.politicianGrid}>
            {politiciansToShow.map((p) => (
              <PoliticianCard key={p.name} politician={p} />
            ))}
          </div>
          {!showAllPoliticians && matchedPoliticians.length > RESULTS_LIMIT && (
            <button
              className={styles.showMore}
              onClick={() => setShowAllPoliticians(true)}
            >
              Show all {matchedPoliticians.length} politicians
            </button>
          )}
        </div>
      )}

      {!isLoading && query && matchedTrades.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Trades</h2>
            <span className={styles.resultCount}>
              {matchedTrades.length} result{matchedTrades.length !== 1 ? "s" : ""}
            </span>
          </div>
          <TradeList trades={tradesToShow} showFilters={false} />
          {!showAllTrades && matchedTrades.length > RESULTS_LIMIT && (
            <button
              className={styles.showMore}
              onClick={() => setShowAllTrades(true)}
            >
              Show all {matchedTrades.length} trades
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default Search;
