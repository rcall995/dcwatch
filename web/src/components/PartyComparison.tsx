import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";
import type { PoliticianSummary } from "@/types";
import styles from "./PartyComparison.module.css";

interface PartyComparisonProps {
  politicians: PoliticianSummary[];
}

interface ComparisonDataPoint {
  metric: string;
  D: number;
  R: number;
  unit: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; payload?: ComparisonDataPoint }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const dataPoint = payload[0]?.payload;
  const unit = dataPoint?.unit || "";
  return (
    <div className={styles.tooltip}>
      <div style={{ color: "#e0e0e0", fontWeight: 600, marginBottom: 6 }}>
        {label}
      </div>
      {payload.map((entry, index) => (
        <div
          key={index}
          style={{ color: entry.color, marginTop: 2 }}
        >
          {entry.name === "D" ? "Democrat" : "Republican"}:{" "}
          {typeof entry.value === "number" ? entry.value.toFixed(1) : entry.value}
          {unit}
        </div>
      ))}
    </div>
  );
}

function PartyComparison({ politicians }: PartyComparisonProps) {
  const data = useMemo(() => {
    const dems = politicians.filter(
      (p) => p.party.toUpperCase() === "D",
    );
    const reps = politicians.filter(
      (p) => p.party.toUpperCase() === "R",
    );

    const avgReturn = (group: PoliticianSummary[]) =>
      group.length > 0
        ? group.reduce((sum, p) => sum + p.est_return_1y, 0) / group.length
        : 0;

    const avgWinRate = (group: PoliticianSummary[]) =>
      group.length > 0
        ? group.reduce((sum, p) => sum + p.win_rate, 0) / group.length
        : 0;

    const totalTrades = (group: PoliticianSummary[]) =>
      group.reduce((sum, p) => sum + p.total_trades, 0);

    const result: ComparisonDataPoint[] = [
      {
        metric: "Avg Return (%)",
        D: avgReturn(dems),
        R: avgReturn(reps),
        unit: "%",
      },
      {
        metric: "Avg Win Rate (%)",
        D: avgWinRate(dems),
        R: avgWinRate(reps),
        unit: "%",
      },
      {
        metric: "Total Trades",
        D: totalTrades(dems),
        R: totalTrades(reps),
        unit: "",
      },
    ];

    return result;
  }, [politicians]);

  if (politicians.length === 0) return null;

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Party Comparison</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={data}
          margin={{ top: 10, right: 30, bottom: 5, left: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis
            dataKey="metric"
            stroke="#888888"
            tick={{ fill: "#e0e0e0", fontSize: 12 }}
          />
          <YAxis
            stroke="#888888"
            tick={{ fill: "#888888", fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Legend
            formatter={(value: string) =>
              value === "D" ? "Democrat" : "Republican"
            }
            wrapperStyle={{ color: "#e0e0e0", fontSize: 13 }}
          />
          <Bar dataKey="D" fill="#2979ff" radius={[4, 4, 0, 0]} />
          <Bar dataKey="R" fill="#ff1744" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PartyComparison;
