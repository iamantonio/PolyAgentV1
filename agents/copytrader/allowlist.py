"""
Market allowlist service - Politics markets only.

Fetches and filters tradeable markets from Polymarket.
Fail-closed: Empty allowlist = no trades allowed.
"""

from typing import List, Optional, TYPE_CHECKING
import logging

# Lazy import to avoid pulling in web3 at module load time
if TYPE_CHECKING:
    from agents.polymarket.gamma import GammaMarketClient

logger = logging.getLogger(__name__)


class AllowlistService:
    """
    Manages dynamic allowlist of tradeable politics markets.

    Option B: Politics-only dynamic allowlist.
    Refreshed on-demand or periodically.
    """

    def __init__(self, gamma_client: Optional["GammaMarketClient"] = None):
        """
        Initialize allowlist service.

        Args:
            gamma_client: Gamma API client (defaults to new instance)
        """
        self.gamma_client = gamma_client  # Will be lazy-loaded if None
        self._allowlist: List[str] = []
        self._last_refresh: Optional[float] = None

    def refresh_politics_markets(self) -> List[str]:
        """
        Refresh allowlist with current politics markets from Polymarket.

        Returns:
            List of allowed market IDs

        Raises:
            RuntimeError: If fetch fails or returns empty list
        """
        try:
            # Lazy import gamma client only when actually refreshing
            if self.gamma_client is None:
                from agents.polymarket.gamma import GammaMarketClient

                self.gamma_client = GammaMarketClient()

            # Fetch all events
            events = self.gamma_client.get_events()

            # Filter for politics category
            politics_markets = []
            for event in events:
                # Check if event has 'tags' or 'category' field indicating politics
                tags = getattr(event, "tags", []) or []
                if isinstance(tags, list):
                    tags = [str(tag).lower() for tag in tags]
                else:
                    tags = []

                # Include if "politics" in tags
                if "politics" in tags or any("politic" in tag for tag in tags):
                    # Get markets for this event
                    if hasattr(event, "markets"):
                        for market in event.markets:
                            if hasattr(market, "id"):
                                politics_markets.append(market.id)

            if not politics_markets:
                logger.error(
                    "Politics market refresh returned empty list. Fail-closed: no trades allowed."
                )
                raise RuntimeError(
                    "Politics allowlist refresh failed: no markets found"
                )

            self._allowlist = politics_markets
            self._last_refresh = __import__("time").time()

            logger.info(
                f"Allowlist refreshed: {len(self._allowlist)} politics markets"
            )
            return self._allowlist

        except Exception as e:
            logger.error(f"Failed to refresh politics allowlist: {e}")
            # Fail-closed: Clear allowlist on error
            self._allowlist = []
            raise RuntimeError(f"Allowlist refresh failed: {e}")

    def is_allowed(self, market_id: str) -> bool:
        """
        Check if market is on allowlist.

        Args:
            market_id: Market ID to check

        Returns:
            True if allowed, False otherwise
        """
        return market_id in self._allowlist

    def get_allowlist(self) -> List[str]:
        """
        Get current allowlist.

        Returns:
            List of allowed market IDs
        """
        return self._allowlist.copy()

    def is_empty(self) -> bool:
        """
        Check if allowlist is empty (fail-closed condition).

        Returns:
            True if allowlist is empty
        """
        return len(self._allowlist) == 0
