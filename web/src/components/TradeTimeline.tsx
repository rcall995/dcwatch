import { useMemo } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { Trade } from "@/types";
import styles from "./TradeTimeline.module.css";

interface TradeTimelineProps {
  trades: Trade[];
}

interface ScatterPoint {
  date: number;
  dateLabel: string;
  est_position: number;
  ticker: string;
  tx_type: string;
  amount_low: number;
  amount_high: number;
  color: string;
}

const TX_COLORS: Record<string, string> = {
  purchase: "#00c853",
  sale_full: "#ff1744",
  sale_partial: "#ff1744",
  exchange: "#00d4ff",
};

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ScatterPoint }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0].payload;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTicker}>{data.ticker}</div>
      <div style={{ color: "#e0e0e0", marginTop: 4 }}>
        {data.tx_type.replace("_", " ")}
      </div>
      <div style={{ color: "#888888", marginTop: 2 }}>{data.dateLabel}</div>
      <div style={{ color: "#888888", marginTop: 2 }}>
        {formatCurrency(data.amount_low)} &ndash;{" "}
        {formatCurrency(data.amount_high)}
      </div>
    </div>
  );
}

function TradeTimeline({ trades }: TradeTimelineProps) {
  const data = useMemo(() => {
    return trades
      .filter((t) => t.tx_date)
      .map((t): ScatterPoint => {
        const est_position = (t.amount_low + t.amount_high) / 2;
        const dateObj = new Date(t.tx_date);
        return {
          date: dateObj.getTime(),
          dateLabel: t.tx_date,
          est_position,
          ticker: t.ticker,
          tx_type: t.tx_type,
          amount_low: t.amount_low,
          amount_high: t.amount_high,
          color: TX_COLORS[t.tx_type] || "#00d4ff",
        };
      })
      .sort((a, b) => a.date - b.date);
  }, [trades]);

  if (data.length === 0) return null;

  const purchases = data.filter((d) => d.tx_type === "purchase");
  const sales = data.filter(
    (d) => d.tx_type === "sale_full" || d.tx_type === "sale_partial",
  );
  const exchanges = data.filter((d) => d.tx_type === "exchange");

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Trade Timeline</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis
            dataKey="date"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(val: number) => {
              const d = new Date(val);
              return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
            }}
            stroke="#888888"
            tick={{ fill: "#888888", fontSize: 12 }}
            name="Date"
          />
          <YAxis
            dataKey="est_position"
            type="number"
            tickFormatter={formatCurrency}
            stroke="#888888"
            tick={{ fill: "#888888", fontSize: 12 }}
            name="Est. Position"
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ strokeDasharray: "3 3", stroke: "#2a2a4a" }}
          />
          {purchases.length > 0 && (
            <Scatter
              name="Purchase"
              data={purchases}
              fill="#00c853"
              shape="circle"
            />
          )}
          {sales.length > 0 && (
            <Scatter
              name="Sale"
              data={sales}
              fill="#ff1744"
              shape="circle"
            />
          )}
          {exchanges.length > 0 && (
            <Scatter
              name="Exchange"
              data={exchanges}
              fill="#00d4ff"
              shape="circle"
            />
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export default TradeTimeline;
