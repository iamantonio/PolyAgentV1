"""
Lightweight validation logger for 72-hour empirical testing experiment.

This is a TEMPORARY module used to measure API failure rates without
adding the full observability stack. After validation experiments complete,
this will be replaced with the production logging system if evidence supports it.

Usage:
    from agents.utils.validation_logger import validation_logger

    try:
        result = api_call()
        validation_logger.log_api_call("endpoint_name", success=True, duration_ms=234.5)
    except Exception as e:
        validation_logger.log_api_call("endpoint_name", success=False, error_msg=str(e))
        raise
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class ValidationLogger:
    """Minimal API call logger for validation experiments"""

    def __init__(self, log_file: str = "logs/validation_experiment.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_api_call(
        self,
        endpoint: str,
        success: bool,
        error_msg: Optional[str] = None,
        duration_ms: float = 0,
        response_count: Optional[int] = None
    ):
        """
        Log an API call result

        Args:
            endpoint: API endpoint identifier (e.g., "gamma_markets", "polymarket", "news")
            success: Whether the call succeeded
            error_msg: Error message if call failed
            duration_ms: Call duration in milliseconds
            response_count: Number of items returned (for detecting incomplete payloads)
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint,
            "success": success,
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
            "response_count": response_count  # Track payload size
        }

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Don't crash if logging fails - observability failures shouldn't break trading
            print(f"[WARNING] Validation logger failed: {e}")


# Global singleton instance
validation_logger = ValidationLogger()
