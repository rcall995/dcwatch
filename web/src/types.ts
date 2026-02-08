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
