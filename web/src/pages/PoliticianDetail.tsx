import { useParams, useNavigate } from "react-router-dom";
import { usePoliticianTrades, useLeaderboard } from "@/hooks/useTradeData";
import PoliticianCard from "@/components/PoliticianCard";
import TradeTimeline from "@/components/TradeTimeline";
import ReturnChart from "@/components/ReturnChart";
import TradeList from "@/components/TradeList";
import LoadingSpinner from "@/components/LoadingSpinner";
import styles from "./PoliticianDetail.module.css";

function PoliticianDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const decodedName = (name || "").replace(/-/g, " ");

  const { data: trades, isLoading: tradesLoading } =
    usePoliticianTrades(decodedName);
  const { data: leaderboard, isLoading: leaderboardLoading } =
    useLeaderboard();

  const summary = leaderboard?.find(
    (p) => p.name.toLowerCase() === decodedName.toLowerCase(),
  );

  const isLoading = tradesLoading || leaderboardLoading;

  return (
    <div className={styles.page}>
      <button className={styles.backButton} onClick={() => navigate(-1)}>
        {"\u2190"} Back
      </button>

      {isLoading && <LoadingSpinner message="Loading politician data..." />}

      {!isLoading && summary && (
        <div className={styles.cardSection}>
          <PoliticianCard politician={summary} />
        </div>
      )}

      {!isLoading && trades && trades.length > 0 && (
        <div>
          <TradeTimeline trades={trades} />
          <ReturnChart trades={trades} />
          <h2 className={styles.sectionTitle}>All Trades</h2>
          <TradeList trades={trades} showFilters={true} />
        </div>
      )}

      {!isLoading && trades && trades.length === 0 && (
        <div className={styles.empty}>
          No trades found for this politician.
        </div>
      )}
    </div>
  );
}

export default PoliticianDetail;
