/**
 * CopyTrader Signal Generator - Main Entry Point
 *
 * ⚠️  SECURITY: This service NEVER accesses private keys.
 *    It ONLY reads public data and emits TradeIntent messages.
 */

import * as dotenv from "dotenv";
import { TradeMonitor } from "./monitor";
import { createOutputHandler } from "./output";

// Load environment
dotenv.config();

// Validate configuration
function validateConfig(): string[] {
  const tradersEnv = process.env.MONITORED_TRADERS;
  if (!tradersEnv) {
    console.error("❌ MONITORED_TRADERS not configured");
    process.exit(1);
  }

  const traders = tradersEnv
    .split(",")
    .map((addr) => addr.trim().toLowerCase())
    .filter((addr) => addr.length > 0);

  if (traders.length === 0) {
    console.error("❌ No valid traders in MONITORED_TRADERS");
    process.exit(1);
  }

  // Validate addresses
  for (const trader of traders) {
    if (!trader.startsWith("0x") || trader.length !== 42) {
      console.error(`❌ Invalid address: ${trader}`);
      process.exit(1);
    }
  }

  return traders;
}

async function main() {
  console.log("=" .repeat(70));
  console.log("COPYTRADER SIGNAL GENERATOR");
  console.log("=" .repeat(70));
  console.log("⚠️  SECURITY: This service has NO access to private keys");
  console.log("⚠️  SECURITY: It ONLY reads public data and emits intents");
  console.log("=" .repeat(70));

  // Validate config
  const traders = validateConfig();
  const pollInterval = parseInt(process.env.POLL_INTERVAL || "1", 10) * 1000;

  console.log(`\n📊 Monitoring ${traders.length} trader(s):`);
  for (const trader of traders) {
    console.log(`   - ${trader}`);
  }
  console.log(`⏱️  Poll interval: ${pollInterval / 1000}s`);

  // Create components
  const monitor = new TradeMonitor(traders);
  const output = createOutputHandler();

  console.log("\n✓ Signal generator started");
  console.log("=" .repeat(70) + "\n");

  // Main loop
  let running = true;
  let checkCount = 0;

  // Handle shutdown
  const shutdown = async () => {
    if (!running) return;
    running = false;

    console.log("\n\n🛑 Shutting down...");
    await output.close();
    console.log("✓ Shutdown complete");
    process.exit(0);
  };

  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);

  // Polling loop
  while (running) {
    try {
      checkCount++;

      // Check for new trades
      const intents = await monitor.checkForNewTrades();

      if (intents.length > 0) {
        console.log(`\n📥 ${intents.length} new trade(s) detected`);

        // Send each intent
        for (const intent of intents) {
          try {
            await output.send(intent);
            console.log(`✓ Sent intent ${intent.intent_id.substring(0, 8)}...`);
          } catch (error) {
            console.error(`✗ Failed to send intent:`, error);
          }
        }
      } else {
        // Show periodic heartbeat
        if (checkCount % 10 === 0) {
          console.log(`⏳ Monitoring... (${checkCount} checks)`);
        }
      }

      // Wait before next check
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    } catch (error) {
      console.error("❌ Error in main loop:", error);
      // Continue running despite errors
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
  }
}

// Run
main().catch((error) => {
  console.error("❌ Fatal error:", error);
  process.exit(1);
});
