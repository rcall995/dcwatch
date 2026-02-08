import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";
import type { Trade } from "@/types";
import styles from "./ReturnChart.module.css";

interface ReturnChartProps {
  trades: Trade[];
}

interface ReturnDataPoint {
  ticker: string;
  est_return: number;
  tx_type: string;
  tx_date: string;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ReturnDataPoint }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0].payload;
  const returnColor = data.est_return >= 0 ? "#00c853" : "#ff1744";
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTicker}>{data.ticker}</div>
      <div style={{ color: returnColor, marginTop: 4, fontWeight: 600 }}>
        {data.est_return >= 0 ? "+" : ""}
        {data.est_return.toFixed(1)}%
      </div>
      <div style={{ color: "#888888", marginTop: 2 }}>
        {data.tx_type.replace("_", " ")} &middot; {data.tx_date}
      </div>
    </div>
  );
}

function ReturnChart({ trades }: ReturnChartProps) {
  const data = useMemo(() => {
    return trades
      .filter((t) => t.est_return != null)
      .sort((a, b) => Math.abs(b.est_return!) - Math.abs(a.est_return!))
      .slice(0, 20)
      .map(
        (t): ReturnDataPoint => ({
          ticker: t.ticker,
          est_return: t.est_return!,
          tx_type: t.tx_type,
          tx_date: t.tx_date,
        }),
      )
      .sort((a, b) => b.est_return - a.est_return);
  }, [trades]);

  if (data.length === 0) return null;

  const chartHeight = Math.max(300, data.length * 28);

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Trade Returns</h3>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, bottom: 5, left: 60 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#2a2a4a"
            horizontal={false}
          />
          <XAxis
            type="number"
            stroke="#888888"
            tick={{ fill: "#888888", fontSize: 12 }}
            tickFormatter={(val: number) => `${val}%`}
          />
          <YAxis
            type="category"
            dataKey="ticker"
            stroke="#888888"
            tick={{ fill: "#e0e0e0", fontSize: 12 }}
            width={55}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
          />
          <Bar dataKey="est_return" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.est_return >= 0 ? "#00c853" : "#ff1744"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ReturnChart;
