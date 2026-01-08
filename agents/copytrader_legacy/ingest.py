"""
Intent ingestion from external signal generators.

Supports two modes:
1. HTTP: Signal generator POSTs intents to /intent endpoint
2. File: Signal generator appends JSON lines to a file, Python tails it

Both modes enforce the same validation firewall.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from queue import Queue, Empty
import threading

from agents.copytrader.schema import TradeIntent
from agents.copytrader.firewall import IntentFirewall, ValidationError
from agents.copytrader.config import CopyTraderConfig

logger = logging.getLogger(__name__)


class IntentIngestor(ABC):
    """
    Base class for intent ingestion.

    Subclasses implement different transport mechanisms (HTTP, file, etc.)
    but all use the same validation firewall.
    """

    def __init__(self, config: CopyTraderConfig):
        self.config = config
        self.firewall = IntentFirewall(config)
        self.validated_intents: Queue[TradeIntent] = Queue()
        self._rejection_count = 0
        self._validation_count = 0

    @abstractmethod
    def start(self) -> None:
        """Start ingesting intents"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop ingesting intents"""
        pass

    def get_next_intent(self, timeout: float = 1.0) -> Optional[TradeIntent]:
        """
        Get next validated intent from queue.

        Returns None if no intent is available within timeout.
        """
        try:
            return self.validated_intents.get(timeout=timeout)
        except Empty:
            return None

    def _process_intent_dict(self, data: dict) -> None:
        """
        Process a raw intent dictionary.

        This is called by subclasses when they receive intent data.
        It handles parsing, validation, and queueing.
        """
        try:
            # Parse schema
            intent = TradeIntent.from_dict(data)

            # Validate through firewall
            self.firewall.validate(intent)

            # Queue for execution
            self.validated_intents.put(intent)
            self._validation_count += 1

            logger.info(
                f"✓ Validated intent {intent.intent_id[:8]}: "
                f"{intent.side} {intent.size_usdc or intent.size_tokens} "
                f"on {intent.market_id[:16]}... from {intent.source_trader[:8]}..."
            )

        except ValidationError as e:
            self._rejection_count += 1
            logger.warning(f"✗ Rejected intent: {e}")

        except Exception as e:
            self._rejection_count += 1
            logger.error(f"✗ Failed to process intent: {e}", exc_info=True)

    def get_stats(self) -> dict:
        """Get ingestion statistics"""
        return {
            "validated_count": self._validation_count,
            "rejected_count": self._rejection_count,
            "queued_count": self.validated_intents.qsize(),
            **self.firewall.get_stats(),
        }


class FileIngestor(IntentIngestor):
    """
    File-based intent ingestion.

    Tails a JSON lines file where each line is a TradeIntent object.
    This is simple and works well for local development and testing.
    """

    def __init__(self, config: CopyTraderConfig, filepath: Path):
        super().__init__(config)
        self.filepath = Path(filepath)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_position = 0

    def start(self) -> None:
        """Start tailing the file"""
        if self._running:
            logger.warning("FileIngestor already running")
            return

        # Create file if it doesn't exist
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.touch(exist_ok=True)

        # Start background thread
        self._running = True
        self._thread = threading.Thread(target=self._tail_file, daemon=True)
        self._thread.start()
        logger.info(f"Started file ingestor: {self.filepath}")

    def stop(self) -> None:
        """Stop tailing the file"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Stopped file ingestor")

    def _tail_file(self) -> None:
        """Background thread that tails the file"""
        while self._running:
            try:
                with open(self.filepath, "r") as f:
                    # Seek to last known position
                    f.seek(self._file_position)

                    # Read new lines
                    for line in f:
                        if not self._running:
                            break

                        line = line.strip()
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            self._process_intent_dict(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in intent file: {e}")

                    # Update position
                    self._file_position = f.tell()

            except Exception as e:
                logger.error(f"Error tailing file: {e}", exc_info=True)

            # Sleep briefly before next check
            if self._running:
                threading.Event().wait(0.1)


class HTTPIngestor(IntentIngestor):
    """
    HTTP-based intent ingestion.

    Runs a simple HTTP server that accepts POST requests to /intent.
    The signal generator POSTs JSON intents to this endpoint.
    """

    def __init__(
        self, config: CopyTraderConfig, host: str = "127.0.0.1", port: int = 8765
    ):
        super().__init__(config)
        self.host = host
        self.port = port
        self._server: Optional[any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start HTTP server"""
        if self._server:
            logger.warning("HTTPIngestor already running")
            return

        from http.server import HTTPServer, BaseHTTPRequestHandler

        ingestor = self  # Capture for handler

        class IntentHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/intent":
                    self.send_response(404)
                    self.end_headers()
                    return

                try:
                    # Read request body
                    content_length = int(self.headers["Content-Length"])
                    body = self.rfile.read(content_length)
                    data = json.loads(body)

                    # Process intent
                    ingestor._process_intent_dict(data)

                    # Success response
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"accepted"}')

                except ValidationError as e:
                    # Validation failed
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    response = json.dumps({"error": str(e)})
                    self.wfile.write(response.encode())

                except Exception as e:
                    # Other error
                    logger.error(f"Error processing HTTP intent: {e}", exc_info=True)
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    response = json.dumps({"error": "Internal server error"})
                    self.wfile.write(response.encode())

            def log_message(self, format, *args):
                # Suppress default logging (we handle it ourselves)
                pass

        # Create and start server
        self._server = HTTPServer((self.host, self.port), IntentHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Started HTTP ingestor: http://{self.host}:{self.port}/intent")

    def stop(self) -> None:
        """Stop HTTP server"""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Stopped HTTP ingestor")


def create_ingestor(
    config: CopyTraderConfig, mode: str = "file", **kwargs
) -> IntentIngestor:
    """
    Factory function to create an ingestor.

    Args:
        config: CopyTrader configuration
        mode: "file" or "http"
        **kwargs: Mode-specific parameters
            For file: filepath (Path)
            For http: host (str), port (int)
    """
    if mode == "file":
        filepath = kwargs.get("filepath", Path("intents.jsonl"))
        return FileIngestor(config, filepath)
    elif mode == "http":
        host = kwargs.get("host", "127.0.0.1")
        port = kwargs.get("port", 8765)
        return HTTPIngestor(config, host, port)
    else:
        raise ValueError(f"Unknown ingestor mode: {mode}")
