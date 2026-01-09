"""
Polymarket Arbitrage Detection Module

Implements risk-free arbitrage strategies:
1. Binary arbitrage: YES + NO < $1.00
2. Multi-outcome arbitrage: All outcomes < $1.00
3. Asymmetric binary (Gabagool): Buy mispriced sides < $0.97

Based on research showing $40M+ extracted via arbitrage in 2024-2025.
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity."""
    market_id: str
    question: str
    opportunity_type: str  # "binary", "multi_outcome", "asymmetric"
    expected_profit_pct: float
    trades: List[Dict[str, any]]  # List of {outcome, price, amount}
    total_cost: Decimal
    guaranteed_return: Decimal
    risk_level: str  # "risk_free", "low_risk"


class ArbitrageDetector:
    """
    Detects arbitrage opportunities in Polymarket markets.

    Profitable when:
    - Binary: YES + NO < $0.99 (1% margin after fees)
    - Multi-outcome: SUM(all outcomes) < $0.99
    - Asymmetric: Single outcome < $0.97 (wait for $1.00 resolution)
    """

    def __init__(
        self,
        min_profit_pct: float = 1.0,  # Minimum 1% profit after fees
        trading_fee_pct: float = 0.01,  # 0.01% Polymarket fee (currently 0)
        gas_cost_usdc: float = 0.10,  # Estimated gas cost per trade
    ):
        self.min_profit_pct = min_profit_pct
        self.trading_fee_pct = trading_fee_pct
        self.gas_cost_usdc = gas_cost_usdc

    def detect_binary_arbitrage(
        self,
        market_id: str,
        question: str,
        yes_price: float,
        no_price: float,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect binary arbitrage: YES + NO should = $1.00

        Profitable when: YES + NO < $0.99 (after fees + gas)

        Example:
        - YES: $0.48
        - NO: $0.50
        - Total: $0.98 → Buy both for $0.98, get $1.00 → 2% profit
        """
        total_cost = Decimal(str(yes_price)) + Decimal(str(no_price))

        # Account for fees and gas
        # FIXED: trading_fee_pct is a percentage (0.01 = 1%), must multiply by total_cost
        fee_amount = total_cost * Decimal(str(self.trading_fee_pct))
        effective_cost = total_cost + fee_amount + Decimal(str(self.gas_cost_usdc))

        # Must be profitable after fees
        if effective_cost >= Decimal('0.99'):
            return None

        profit_pct = float((Decimal('1.00') - effective_cost) / effective_cost * 100)

        if profit_pct < self.min_profit_pct:
            return None

        return ArbitrageOpportunity(
            market_id=market_id,
            question=question,
            opportunity_type="binary",
            expected_profit_pct=profit_pct,
            trades=[
                {"outcome": "YES", "price": yes_price, "amount": 1.0},
                {"outcome": "NO", "price": no_price, "amount": 1.0},
            ],
            total_cost=effective_cost,
            guaranteed_return=Decimal('1.00'),
            risk_level="risk_free"
        )

    def detect_multi_outcome_arbitrage(
        self,
        market_id: str,
        question: str,
        outcome_prices: Dict[str, float],
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect multi-outcome arbitrage: SUM(all outcomes) should = $1.00

        Profitable when: SUM < $0.99 (after fees + gas)

        Example (4 outcomes):
        - Outcome A: $0.20
        - Outcome B: $0.25
        - Outcome C: $0.30
        - Outcome D: $0.20
        - Total: $0.95 → Buy all for $0.95, get $1.00 → 5% profit
        """
        total_cost = sum(Decimal(str(price)) for price in outcome_prices.values())

        # Account for fees and gas (multiple trades)
        num_outcomes = len(outcome_prices)
        # FIXED: trading_fee_pct is a percentage (0.01 = 1%), must multiply by total_cost
        total_fees = total_cost * Decimal(str(self.trading_fee_pct))
        total_gas = Decimal(str(self.gas_cost_usdc * num_outcomes))
        effective_cost = total_cost + total_fees + total_gas

        # Must be profitable after fees
        if effective_cost >= Decimal('0.99'):
            return None

        profit_pct = float((Decimal('1.00') - effective_cost) / effective_cost * 100)

        if profit_pct < self.min_profit_pct:
            return None

        trades = [
            {"outcome": outcome, "price": price, "amount": 1.0}
            for outcome, price in outcome_prices.items()
        ]

        return ArbitrageOpportunity(
            market_id=market_id,
            question=question,
            opportunity_type="multi_outcome",
            expected_profit_pct=profit_pct,
            trades=trades,
            total_cost=effective_cost,
            guaranteed_return=Decimal('1.00'),
            risk_level="risk_free"
        )

    def detect_asymmetric_binary(
        self,
        market_id: str,
        question: str,
        yes_price: float,
        no_price: float,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect asymmetric binary opportunity (Gabagool strategy).

        Buy mispriced side < $0.97, wait for $1.00 resolution.
        Not risk-free, but high probability profit.

        Example:
        - YES: $0.95 (too cheap!)
        - Buy YES for $0.95, if correct → $1.00 = 5% profit
        - Risk: If wrong, lose $0.95
        """
        # Check if either side is mispriced (< $0.97)
        opportunities = []

        if yes_price < 0.97:
            profit_pct = ((1.00 - yes_price) / yes_price) * 100
            if profit_pct >= self.min_profit_pct:
                opportunities.append(("YES", yes_price, profit_pct))

        if no_price < 0.97:
            profit_pct = ((1.00 - no_price) / no_price) * 100
            if profit_pct >= self.min_profit_pct:
                opportunities.append(("NO", no_price, profit_pct))

        if not opportunities:
            return None

        # Pick the cheaper side (higher potential profit)
        best_side, best_price, best_profit = min(opportunities, key=lambda x: x[1])

        return ArbitrageOpportunity(
            market_id=market_id,
            question=question,
            opportunity_type="asymmetric",
            expected_profit_pct=best_profit,
            trades=[
                {"outcome": best_side, "price": best_price, "amount": 1.0},
            ],
            total_cost=Decimal(str(best_price)),
            guaranteed_return=Decimal('1.00'),  # If outcome correct
            risk_level="low_risk"  # Requires outcome to be correct
        )

    def scan_market(
        self,
        market_id: str,
        question: str,
        outcome_prices: Dict[str, float],
    ) -> List[ArbitrageOpportunity]:
        """
        Scan a single market for ALL arbitrage opportunities.

        Returns list of opportunities sorted by profit potential.
        """
        opportunities = []

        # Check binary arbitrage (if exactly 2 outcomes)
        if len(outcome_prices) == 2:
            outcomes = list(outcome_prices.keys())
            yes_price = outcome_prices.get("Yes", outcome_prices.get(outcomes[0]))
            no_price = outcome_prices.get("No", outcome_prices.get(outcomes[1]))

            # Binary arbitrage (risk-free)
            binary_arb = self.detect_binary_arbitrage(market_id, question, yes_price, no_price)
            if binary_arb:
                opportunities.append(binary_arb)

            # Asymmetric binary (low risk)
            asym_arb = self.detect_asymmetric_binary(market_id, question, yes_price, no_price)
            if asym_arb:
                opportunities.append(asym_arb)

        # Check multi-outcome arbitrage (3+ outcomes)
        elif len(outcome_prices) > 2:
            multi_arb = self.detect_multi_outcome_arbitrage(market_id, question, outcome_prices)
            if multi_arb:
                opportunities.append(multi_arb)

        # Sort by risk level (risk-free first) then profit %
        opportunities.sort(
            key=lambda x: (
                0 if x.risk_level == "risk_free" else 1,
                -x.expected_profit_pct
            )
        )

        return opportunities
