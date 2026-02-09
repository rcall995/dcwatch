export interface Trade {
  id: string;
  politician: string;
  party: string;
  state: string;
  chamber: "house" | "senate";
  ticker: string;
  asset_description: string;
  asset_type: "stock" | "option" | "etf" | "bond" | "other";
  tx_type: "purchase" | "sale_full" | "sale_partial" | "exchange";
  tx_date: string;
  disclosure_date: string;
  amount_low: number;
  amount_high: number;
  owner: string;
  filing_url: string;
  is_amended: boolean;
  days_late: number;
  price_at_trade?: number;
  current_price?: number;
  est_return?: number;
}

export interface PoliticianSummary {
  name: string;
  party: string;
  state: string;
  chamber: "house" | "senate";
  total_trades: number;
  est_return_1y: number;
  win_rate: number;
  best_trade: { ticker: string; est_return: number } | null;
  worst_trade: { ticker: string; est_return: number } | null;
  total_volume_low: number;
  total_volume_high: number;
}

export interface Signal {
  ticker: string;
  company_name: string;
  politicians: { name: string; party: string; tx_type: string; tx_date: string }[];
  start_date: string;
  end_date: string;
  heat_score: number;
  bipartisan: boolean;
}

export interface MockTrade {
  id: string;
  trade_id: string;
  ticker: string;
  politician: string;
  tx_type: "buy" | "sell";
  entry_price: number;
  current_price: number;
  created_at: string;
  notes: string;
}

export interface TopPick {
  ticker: string;
  company_name: string;
  score: number;
  num_politicians: number;
  bipartisan: boolean;
  avg_win_rate: number;
  latest_trade_date: string;
  price_at_latest: number | null;
  current_price: number | null;
  politicians: { name: string; party: string; tx_date: string; win_rate: number }[];
}

export interface CommitteeMatch {
  id: string;
  name: string;
  sectors: string[];
  match_type: "ticker" | "keyword";
  matched_on: string;
}

export interface CommitteeCorrelation {
  trade_id: string;
  politician: string;
  party: string;
  state: string;
  chamber: "house" | "senate";
  ticker: string;
  asset_description: string;
  tx_type: string;
  tx_date: string;
  amount_low: number;
  amount_high: number;
  days_late: number;
  committees: CommitteeMatch[];
  correlation_score: number;
  est_return: number | null;
}

export interface CorrelationSummary {
  total_correlated_trades: number;
  total_politicians_flagged: number;
  pct_of_all_trades: number;
  top_committees: { name: string; trade_count: number }[];
  top_politicians: { name: string; party: string; correlated_count: number }[];
}

export interface CommitteeCorrelationsData {
  correlations: CommitteeCorrelation[];
  summary: CorrelationSummary;
}

export interface PoliticianCommittee {
  committee_id: string;
  committee_name: string;
  rank: number;
  title: string;
}

export interface PoliticianCommitteeData {
  bioguide_id: string;
  name: string;
  party: string;
  state: string;
  chamber: string;
  committees: PoliticianCommittee[];
}

export interface CommitteesData {
  committees: Record<string, { id: string; name: string; chamber: string; jurisdiction: string; url: string }>;
  politicians: Record<string, PoliticianCommitteeData>;
}

export interface Hearing {
  committee: string;
  committee_id: string;
  title: string;
  date: string;
  chamber: string;
  url: string;
}

export interface HearingsData {
  hearings: Hearing[];
}

export interface BacktestTrade {
  id: string;
  politician: string;
  party: string;
  ticker: string;
  asset_description: string;
  tx_date: string;
  disclosure_date: string;
  days_late: number;
  amount_low: number;
  amount_high: number;
  price_at_trade: number | null;
  price_at_disclosure: number | null;
  price_30d: number | null;
  price_90d: number | null;
  current_price: number | null;
  politician_return: number | null;
  copycat_return_current: number | null;
  copycat_return_30d: number | null;
  copycat_return_90d: number | null;
  spy_return_current: number | null;
  spy_return_30d: number | null;
  spy_return_90d: number | null;
  alpha_current: number | null;
  alpha_30d: number | null;
  alpha_90d: number | null;
  timing_cost: number | null;
}

export interface WindowStats {
  count: number;
  win_rate: number;
  avg_return: number;
  median_return: number;
}

export interface BenchmarkComparison {
  copycat_avg: number;
  spy_avg: number;
  alpha: number;
  beat_spy_pct: number;
}

export interface PartyBreakdown {
  [party: string]: WindowStats;
}

export interface AmountBreakdown {
  [size: string]: WindowStats;
}

export interface YearBreakdown extends WindowStats {
  year: number;
}

export interface DaysLateBreakdown extends WindowStats {
  bucket: string;
}

export interface BacktestData {
  generated_at: string;
  total_trades_analyzed: number;
  strategy_summary: {
    current: WindowStats;
    "30d": WindowStats;
    "90d": WindowStats;
  };
  vs_benchmark: {
    current: BenchmarkComparison;
    "30d": BenchmarkComparison;
    "90d": BenchmarkComparison;
  };
  politician_vs_copycat: {
    avg_politician_return: number;
    avg_copycat_return: number;
    avg_timing_cost: number;
    pct_where_delay_hurt: number;
  };
  by_party: PartyBreakdown;
  by_amount: AmountBreakdown;
  by_year: YearBreakdown[];
  by_days_late: DaysLateBreakdown[];
  top_trades: {
    best: BacktestTrade[];
    worst: BacktestTrade[];
  };
  individual_trades: BacktestTrade[];
}
