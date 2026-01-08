/**
 * Intent output handlers.
 *
 * Supports two modes:
 * - File: Append JSON lines to a file
 * - HTTP: POST JSON to Python executor endpoint
 */

import * as fs from "fs";
import * as path from "path";
import fetch from "cross-fetch";
import { TradeIntent } from "./types";

export interface OutputHandler {
  send(intent: TradeIntent): Promise<void>;
  close(): Promise<void>;
}

/**
 * File output handler - appends JSON lines to a file.
 */
export class FileOutputHandler implements OutputHandler {
  private filePath: string;
  private stream: fs.WriteStream;

  constructor(filePath: string) {
    this.filePath = path.resolve(filePath);

    // Ensure parent directory exists
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Open file for appending
    this.stream = fs.createWriteStream(this.filePath, { flags: "a" });

    console.log(`📁 File output: ${this.filePath}`);
  }

  async send(intent: TradeIntent): Promise<void> {
    const line = JSON.stringify(intent) + "\n";
    return new Promise((resolve, reject) => {
      this.stream.write(line, (err) => {
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }

  async close(): Promise<void> {
    return new Promise((resolve) => {
      this.stream.end(() => resolve());
    });
  }
}

/**
 * HTTP output handler - POSTs JSON to Python executor.
 */
export class HTTPOutputHandler implements OutputHandler {
  private endpoint: string;
  private timeout: number;

  constructor(endpoint: string, timeout: number = 5000) {
    this.endpoint = endpoint;
    this.timeout = timeout;

    console.log(`🌐 HTTP output: ${this.endpoint}`);
  }

  async send(intent: TradeIntent): Promise<void> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(this.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(intent),
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`HTTP ${response.status}: ${error}`);
      }

      const result = await response.json();
      console.log(`✓ Intent accepted:`, result);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async close(): Promise<void> {
    // No cleanup needed for HTTP
  }
}

/**
 * Create output handler based on configuration.
 */
export function createOutputHandler(): OutputHandler {
  const mode = process.env.OUTPUT_MODE || "file";

  if (mode === "http") {
    const endpoint =
      process.env.PYTHON_ENDPOINT || "http://127.0.0.1:8765/intent";
    return new HTTPOutputHandler(endpoint);
  } else {
    const filePath = process.env.OUTPUT_FILE || "../../intents.jsonl";
    return new FileOutputHandler(filePath);
  }
}
