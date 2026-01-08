/**
 * TypeScript types matching the Python TradeIntent schema.
 *
 * These must stay in sync with agents/copytrader/schema.py
 */

export interface TradeIntentMetadata {
  best_bid?: number;
  best_ask?: number;
  detection_latency_ms?: number;
  trader_position_size?: number;
  trader_balance_usd?: number;
  trader_order_usd?: number;
  source_tx_hash?: string;
  extra?: Record<string, any>;
}

export interface TradeIntent {
  intent_id: string;
  timestamp: string; // ISO 8601
  source_trader: string;
  market_id: string;
  outcome: "YES" | "NO";
  side: "BUY" | "SELL";
  price_limit?: number;
  size_usdc?: number;
  size_tokens?: number;
  metadata: TradeIntentMetadata;
}

export interface TraderPosition {
  asset: string;
  conditionId: string;
  size: number;
  avgPrice: number;
  currentValue: number;
  slug?: string;
  outcome?: string;
}

export interface TraderActivity {
  timestamp: number;
  type: string;
  size: number;
  usdcSize: number;
  transactionHash: string;
  price: number;
  asset: string;
  side: "BUY" | "SELL";
  conditionId: string;
  outcome: string;
}

export interface OrderBook {
  asset: string;
  bids: Array<{ price: string; size: string }>;
  asks: Array<{ price: string; size: string }>;
}
