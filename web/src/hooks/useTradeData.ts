import { useQuery } from "@tanstack/react-query";
import type { Trade, PoliticianSummary, Signal } from "@/types";

/**
 * Base URL for data files.
 * Defaults to "/data" (served from public/data/ in production).
 * Override with VITE_DATA_URL env var for development or external data sources.
 */
const DATA_BASE_URL = import.meta.env.VITE_DATA_URL || "/data";

async function fetchJson<T>(path: string): Promise<T> {
  const url = `${DATA_BASE_URL}/${path}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

/**
 * Fetch the latest trades (small payload, refreshed frequently).
 */
export function useLatestTrades() {
  return useQuery<Trade[]>({
    queryKey: ["trades", "latest"],
    queryFn: () => fetchJson<Trade[]>("latest.json"),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Fetch the full trades dataset (large payload, cached aggressively).
 */
export function useTrades() {
  return useQuery<Trade[]>({
    queryKey: ["trades", "all"],
    queryFn: () => fetchJson<Trade[]>("trades.json"),
    staleTime: 15 * 60 * 1000, // 15 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  });
}

/**
 * Fetch the leaderboard / politician summary data.
 */
export function useLeaderboard() {
  return useQuery<PoliticianSummary[]>({
    queryKey: ["leaderboard"],
    queryFn: () => fetchJson<PoliticianSummary[]>("summary.json"),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Fetch cluster signals (multiple politicians trading same ticker).
 */
export function useSignals() {
  return useQuery<Signal[]>({
    queryKey: ["signals"],
    queryFn: () => fetchJson<Signal[]>("signals.json"),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Get trades filtered by politician name.
 * Depends on the full trades dataset being loaded.
 */
export function usePoliticianTrades(name: string) {
  const tradesQuery = useTrades();

  return useQuery<Trade[]>({
    queryKey: ["trades", "politician", name],
    queryFn: () => {
      if (!tradesQuery.data) {
        return [];
      }
      const normalizedName = name.toLowerCase().replace(/-/g, " ");
      return tradesQuery.data.filter(
        (trade) => trade.politician.toLowerCase() === normalizedName,
      );
    },
    enabled: !!tradesQuery.data && !!name,
    staleTime: 15 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}
