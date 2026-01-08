/**
 * Trade monitoring logic.
 *
 * Detects new trades by comparing positions over time.
 */

import { v4 as uuidv4 } from "uuid";
import {
  TradeIntent,
  TraderPosition,
  TraderActivity,
  TradeIntentMetadata,
} from "./types";
import {
  fetchTraderPositions,
  fetchTraderActivity,
  fetchOrderBook,
} from "./api";

/**
 * State tracker for each monitored trader.
 */
class TraderState {
  address: string;
  lastPositions: Map<string, TraderPosition> = new Map();
  lastActivityCheck: number = Date.now();
  seenTxHashes: Set<string> = new Set();

  constructor(address: string) {
    this.address = address;
  }

  async detectNewTrades(): Promise<TradeIntent[]> {
    const intents: TradeIntent[] = [];

    try {
      // Fetch recent activity
      const activities = await fetchTraderActivity(this.address);

      // Filter for new trades
      for (const activity of activities) {
        // Skip if we've already seen this transaction
        if (this.seenTxHashes.has(activity.transactionHash)) {
          continue;
        }

        // Skip if too old (e.g., > 1 hour)
        const ageSeconds = (Date.now() - activity.timestamp * 1000) / 1000;
        if (ageSeconds > 3600) {
          continue;
        }

        // Mark as seen
        this.seenTxHashes.add(activity.transactionHash);

        // Create intent
        const intent = await this.createIntent(activity);
        if (intent) {
          intents.push(intent);
        }
      }

      // Cleanup old tx hashes (keep last 1000)
      if (this.seenTxHashes.size > 1000) {
        const toKeep = Array.from(this.seenTxHashes).slice(-1000);
        this.seenTxHashes = new Set(toKeep);
      }
    } catch (error) {
      console.error(`Error detecting trades for ${this.address}:`, error);
    }

    return intents;
  }

  private async createIntent(
    activity: TraderActivity
  ): Promise<TradeIntent | null> {
    try {
      // Fetch current positions to get context
      const positions = await fetchTraderPositions(this.address);
      const position = positions.find(
        (p) => p.conditionId === activity.conditionId
      );

      // Build metadata
      const metadata: TradeIntentMetadata = {
        trader_order_usd: activity.usdcSize,
        trader_position_size: position?.size || 0,
        source_tx_hash: activity.transactionHash,
        detection_latency_ms: Date.now() - activity.timestamp * 1000,
      };

      // Try to get orderbook for price context
      try {
        const orderbook = await fetchOrderBook(activity.asset);
        if (orderbook.bids.length > 0) {
          metadata.best_bid = parseFloat(
            orderbook.bids[0].price
          );
        }
        if (orderbook.asks.length > 0) {
          metadata.best_ask = parseFloat(
            orderbook.asks[0].price
          );
        }
      } catch (e) {
        // Orderbook fetch failed - continue without it
      }

      // Create intent
      const intent: TradeIntent = {
        intent_id: uuidv4(),
        timestamp: new Date().toISOString(),
        source_trader: this.address.toLowerCase(),
        market_id: activity.conditionId,
        outcome: activity.outcome === "Yes" ? "YES" : "NO",
        side: activity.side,
        price_limit: activity.price,
        size_usdc: activity.side === "BUY" ? activity.usdcSize : undefined,
        size_tokens: activity.side === "SELL" ? activity.size : undefined,
        metadata,
      };

      console.log(
        `📤 Intent created: ${activity.side} $${activity.usdcSize.toFixed(2)} from ${this.address.substring(0, 8)}...`
      );

      return intent;
    } catch (error) {
      console.error("Error creating intent:", error);
      return null;
    }
  }
}

/**
 * Multi-trader monitor.
 */
export class TradeMonitor {
  private traders: Map<string, TraderState> = new Map();

  constructor(traderAddresses: string[]) {
    for (const address of traderAddresses) {
      this.traders.set(address.toLowerCase(), new TraderState(address));
    }
  }

  async checkForNewTrades(): Promise<TradeIntent[]> {
    const allIntents: TradeIntent[] = [];

    for (const [address, state] of this.traders) {
      const intents = await state.detectNewTrades();
      allIntents.push(...intents);
    }

    return allIntents;
  }
}
