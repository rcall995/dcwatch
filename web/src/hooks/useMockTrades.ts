import { useState, useCallback, useEffect } from "react";
import type { Trade, MockTrade } from "@/types";

const STORAGE_KEY = "dc-watcher-mock-trades";

function loadMockTrades(): MockTrade[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveMockTrades(trades: MockTrade[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trades));
}

export function useMockTrades() {
  const [mockTrades, setMockTrades] = useState<MockTrade[]>(loadMockTrades);

  useEffect(() => {
    saveMockTrades(mockTrades);
  }, [mockTrades]);

  const addMockTrade = useCallback(
    (trade: Trade, direction: "buy" | "sell", notes = "") => {
      const newMock: MockTrade = {
        id: crypto.randomUUID(),
        trade_id: trade.id,
        ticker: trade.ticker,
        politician: trade.politician,
        tx_type: direction,
        entry_price: trade.price_at_trade ?? 0,
        current_price: trade.current_price ?? trade.price_at_trade ?? 0,
        created_at: new Date().toISOString(),
        notes,
      };
      setMockTrades((prev) => [...prev, newMock]);
    },
    [],
  );

  const removeMockTrade = useCallback((id: string) => {
    setMockTrades((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const updatePrices = useCallback((trades: Trade[]) => {
    setMockTrades((prev) =>
      prev.map((mock) => {
        const latest = trades.find((t) => t.ticker === mock.ticker);
        if (latest?.current_price != null) {
          return { ...mock, current_price: latest.current_price };
        }
        return mock;
      }),
    );
  }, []);

  return { mockTrades, addMockTrade, removeMockTrade, updatePrices };
}
