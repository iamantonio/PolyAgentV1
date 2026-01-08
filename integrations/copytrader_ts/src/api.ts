/**
 * Polymarket Data API client (PUBLIC data only).
 *
 * This client ONLY reads public data. It has NO access to private keys.
 */

import fetch from "cross-fetch";
import { TraderPosition, TraderActivity, OrderBook } from "./types";

const DATA_API_URL =
  process.env.DATA_API_URL || "https://data-api.polymarket.com";

export async function fetchTraderPositions(
  address: string
): Promise<TraderPosition[]> {
  const url = `${DATA_API_URL}/positions?user=${address}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch positions: ${response.statusText}`);
  }

  return (await response.json()) as TraderPosition[];
}

export async function fetchTraderActivity(
  address: string
): Promise<TraderActivity[]> {
  const url = `${DATA_API_URL}/activity?user=${address}&type=TRADE`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch activity: ${response.statusText}`);
  }

  return (await response.json()) as TraderActivity[];
}

export async function fetchOrderBook(asset: string): Promise<OrderBook> {
  // Note: This would need the actual CLOB API endpoint
  // For now, return empty orderbook as placeholder
  console.warn("OrderBook fetching not implemented - using placeholder");
  return {
    asset,
    bids: [],
    asks: [],
  };
}
