"""
Multi-Agent Reasoning System

Prevents prediction errors through multiple verification steps:
1. Predictor: Makes initial forecast
2. Critic: Red team challenges the prediction
3. Synthesizer: Makes final decision with verification
4. Verification: Catches logical errors before execution

This makes backwards trades IMPOSSIBLE.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os
from openai import OpenAI

@dataclass
class Prediction:
    """Prediction from the first agent"""
    outcome: str  # "Yes" or "No"
    probability: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    reasoning: str
    supporting_evidence: List[str]
    contradicting_evidence: List[str]

@dataclass
class Critique:
    """Critique from the red team agent"""
    challenges: List[str]
    alternative_hypotheses: List[str]
    confidence_assessment: str  # "too high", "appropriate", "too low"
    recommended_adjustment: float  # adjustment to probability
    red_flags: List[str]

@dataclass
class FinalDecision:
    """Final decision after synthesis"""
    outcome_to_buy: str  # "Yes" or "No" - WHAT TO BUY
    probability: float
    confidence: float
    reasoning: str
    verification: str  # Explicit check that outcome matches prediction


class MultiAgentReasoning:
    """
    Multi-agent reasoning system that prevents errors through verification.

    Process:
    1. Predictor makes forecast
    2. Critic challenges it
    3. Synthesizer makes decision
    4. Verification catches errors
    """

    def __init__(self, openai_api_key: Optional[str] = None, use_xai: bool = True):
        """
        Initialize multi-agent reasoning with XAI (Grok) or OpenAI.

        Args:
            openai_api_key: API key (optional, reads from env)
            use_xai: If True, use XAI/Grok (default). If False, use OpenAI.
        """
        self.use_xai = use_xai

        if use_xai:
            # Use XAI (Grok-4) - OpenAI-compatible API
            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                raise ValueError("XAI_API_KEY not found in environment")

            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1"
            )
            self.model = "grok-4-1-fast-reasoning"  # XAI's reasoning model
            self.provider = "XAI (Grok-4.1-Fast-Reasoning)"
        else:
            # Use OpenAI
            if openai_api_key is None:
                openai_api_key = os.getenv("OPENAI_API_KEY")

            self.client = OpenAI(api_key=openai_api_key)
            self.model = "gpt-4"
            self.provider = "OpenAI"

    def health_check(self) -> Tuple[bool, str]:
        """
        Test API access before trading.
        Returns (is_healthy: bool, error_message: str)

        Distinguishes between:
        - insufficient_quota (need credits)
        - wrong org/project (config)
        - rate_limit (backoff)
        """
        try:
            # Use appropriate test model based on provider
            if self.use_xai:
                healthcheck_model = "grok-4-1-fast-reasoning"
            else:
                healthcheck_model = os.getenv("OPENAI_HEALTHCHECK_MODEL", "gpt-4o-mini")

            # Minimal test call (costs ~$0.0001)
            response = self.client.chat.completions.create(
                model=healthcheck_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return (True, f"OK - Using {self.provider}")

        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__

            # Structured error classification (prefer attributes over string parsing)
            error_code = getattr(e, 'code', None)
            error_status = getattr(e, 'status_code', None)
            error_body = getattr(e, 'body', {})

            # Extract structured error info if available
            if isinstance(error_body, dict):
                error_message = error_body.get('message', error_str)
                error_param = error_body.get('param', None)
                error_code_body = error_body.get('code', error_code)
            else:
                error_message = error_str
                error_param = None
                error_code_body = error_code

            # Classify by status code and structured fields first
            if error_status == 429 or "RateLimitError" in error_type:
                # Distinguish quota vs rate-limit using structured fields
                if error_code == "insufficient_quota" or (error_code_body and "quota" in str(error_code_body).lower()):
                    return (False,
                        f"QUOTA DEPLETED (HTTP 429, code: {error_code_body})\n"
                        f"Fix: Add credits at https://platform.openai.com/account/billing/overview\n"
                        f"Message: {error_message}")
                elif error_code == "rate_limit_exceeded" or "rate_limit" in error_message.lower():
                    return (False,
                        f"RATE LIMIT EXCEEDED (HTTP 429, code: {error_code_body})\n"
                        f"Fix: Wait and retry, or increase limits\n"
                        f"Message: {error_message}")
                else:
                    # Unknown 429 - report structured data
                    return (False,
                        f"429 ERROR (unknown cause)\n"
                        f"Status: {error_status}, Code: {error_code_body}, Type: {error_type}\n"
                        f"Message: {error_message}")

            elif error_status == 401 or "AuthenticationError" in error_type:
                api_key_var = "XAI_API_KEY" if self.use_xai else "OPENAI_API_KEY"
                return (False,
                    f"AUTH FAILED (HTTP 401)\n"
                    f"Fix: Check {api_key_var} or org/project settings\n"
                    f"Message: {error_message}")

            elif error_status == 403 or "PermissionDeniedError" in error_type:
                return (False,
                    f"PERMISSION DENIED (HTTP 403)\n"
                    f"Fix: Check org/project permissions or model access\n"
                    f"Message: {error_message}")

            elif error_status == 404 or "NotFoundError" in error_type:
                provider_hint = "grok-4-1-fast-reasoning for XAI" if self.use_xai else "gpt-4o-mini for OpenAI"
                return (False,
                    f"MODEL NOT FOUND (HTTP 404)\n"
                    f"Fix: Use correct model ({provider_hint})\n"
                    f"Model tried: {healthcheck_model}\n"
                    f"Message: {error_message}")

            else:
                # Fallback for unknown errors - provide full structured info
                return (False,
                    f"API ERROR: {error_type}\n"
                    f"Status: {error_status}, Code: {error_code_body}\n"
                    f"Message: {error_message}")

    def predict(
        self,
        question: str,
        description: str,
        market_data: Dict,
        social_data: Optional[Dict] = None
    ) -> Prediction:
        """
        Agent 1: Make initial prediction

        This agent analyzes the market and makes a forecast.
        It explicitly states what outcome it thinks will happen.
        """

        prompt = f"""You are a prediction agent analyzing a prediction market.

Market Question: {question}
Description: {description}

Market Data:
- Current Prices: {market_data.get('prices', {})}
- Volume: {market_data.get('volume', 'Unknown')}
- Time to Close: {market_data.get('time_to_close_hours', 'Unknown')} hours

{f"Social Data: {social_data}" if social_data else ""}

Your task: Predict which outcome will happen.

CRITICAL: Be explicit about what you think will happen.
- If you think YES is more likely, say "I predict outcome: YES"
- If you think NO is more likely, say "I predict outcome: NO"

Provide:
1. Your prediction (YES or NO)
2. Probability (0.0 to 1.0)
3. Confidence level (0.0 to 1.0)
4. Reasoning
5. Supporting evidence (what supports this prediction)
6. Contradicting evidence (what argues against it)

Format:
PREDICTION: [YES or NO]
PROBABILITY: [0.0 to 1.0]
CONFIDENCE: [0.0 to 1.0]
REASONING: [your analysis]
SUPPORTING: [evidence for this prediction]
CONTRADICTING: [evidence against this prediction]
"""

        response = self.client.chat.completions.create(
            model=self.model,  # Use configured model (grok-beta or gpt-4)
            messages=[
                {"role": "system", "content": "You are an expert prediction analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )

        content = response.choices[0].message.content

        # Parse response (with robust error handling for micro-markets)
        outcome = self._extract_field(content, "PREDICTION")

        # Try to parse probability, default to 0.5 if LLM returns "N/A" or similar
        try:
            prob_str = self._extract_field(content, "PROBABILITY", "0.5")
            # Remove brackets, ranges, or other formatting
            prob_str = prob_str.strip("[]").split()[0]  # Take first number if range
            probability = float(prob_str)
        except (ValueError, AttributeError, IndexError):
            probability = 0.5  # Default to 50% for unpredictable micro-markets

        try:
            conf_str = self._extract_field(content, "CONFIDENCE", "0.5")
            conf_str = conf_str.strip("[]").split()[0]
            confidence = float(conf_str)
        except (ValueError, AttributeError, IndexError):
            confidence = 0.5

        reasoning = self._extract_field(content, "REASONING", "")
        supporting = self._extract_field(content, "SUPPORTING", "").split("\n")
        contradicting = self._extract_field(content, "CONTRADICTING", "").split("\n")

        return Prediction(
            outcome=outcome.strip().upper(),
            probability=probability,
            confidence=confidence,
            reasoning=reasoning,
            supporting_evidence=[s for s in supporting if s.strip()],
            contradicting_evidence=[c for c in contradicting if c.strip()]
        )

    def critique(
        self,
        question: str,
        prediction: Prediction
    ) -> Critique:
        """
        Agent 2: Red team the prediction

        This agent challenges the prediction and looks for errors.
        It acts as a skeptical peer reviewer.
        """

        prompt = f"""You are a critic agent reviewing a prediction. Your job is to find flaws.

Market Question: {question}

PREDICTION TO REVIEW:
- Predicted Outcome: {prediction.outcome}
- Probability: {prediction.probability:.0%}
- Confidence: {prediction.confidence:.0%}
- Reasoning: {prediction.reasoning}

Your task: Challenge this prediction ruthlessly.

Questions to ask:
1. What could make this prediction wrong?
2. Is the confidence level justified?
3. Are there alternative explanations?
4. What evidence contradicts this view?
5. Is the analyst anchoring on recent events?
6. Are they overconfident or underconfident?

Provide:
1. Challenges (specific problems with the prediction)
2. Alternative hypotheses (other possible outcomes)
3. Confidence assessment (is confidence too high/low/appropriate?)
4. Recommended adjustment to probability
5. Red flags (major concerns)

Format:
CHALLENGES: [list problems]
ALTERNATIVES: [other hypotheses]
CONFIDENCE: [too high/appropriate/too low]
ADJUSTMENT: [+/- adjustment to probability]
RED_FLAGS: [major concerns]
"""

        response = self.client.chat.completions.create(
            model=self.model,  # Use configured model (grok-beta or gpt-4)
            messages=[
                {"role": "system", "content": "You are a skeptical critic finding flaws in predictions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )

        content = response.choices[0].message.content

        challenges = self._extract_field(content, "CHALLENGES", "").split("\n")
        alternatives = self._extract_field(content, "ALTERNATIVES", "").split("\n")
        confidence_assessment = self._extract_field(content, "CONFIDENCE", "appropriate")
        adjustment_str = self._extract_field(content, "ADJUSTMENT", "0")
        red_flags = self._extract_field(content, "RED_FLAGS", "").split("\n")

        # Parse adjustment
        try:
            adjustment = float(adjustment_str.replace("%", "").replace("+", ""))
            if "%" in adjustment_str:
                adjustment = adjustment / 100.0
        except:
            adjustment = 0.0

        return Critique(
            challenges=[c for c in challenges if c.strip()],
            alternative_hypotheses=[a for a in alternatives if a.strip()],
            confidence_assessment=confidence_assessment.lower(),
            recommended_adjustment=adjustment,
            red_flags=[r for r in red_flags if r.strip()]
        )

    def synthesize(
        self,
        question: str,
        prediction: Prediction,
        critique: Critique
    ) -> FinalDecision:
        """
        Agent 3: Make final decision

        This agent combines prediction and critique to make the final call.
        It includes explicit verification to catch logical errors.
        """

        prompt = f"""You are a synthesis agent making a final trading decision.

Market Question: {question}

ORIGINAL PREDICTION:
- Outcome: {prediction.outcome}
- Probability: {prediction.probability:.0%}
- Reasoning: {prediction.reasoning}

CRITIC'S FEEDBACK:
- Challenges: {', '.join(critique.challenges)}
- Confidence Assessment: {critique.confidence_assessment}
- Recommended Adjustment: {critique.recommended_adjustment:+.0%}

Your task: Make the FINAL decision on what to buy.

CRITICAL VERIFICATION:
- If you think YES is more likely → BUY YES
- If you think NO is more likely → BUY NO
- NEVER buy the LESS likely outcome
- This is NOT about finding value bets
- This IS about buying what you think will happen

Provide:
1. Outcome to BUY (YES or NO)
2. Final probability
3. Final confidence
4. Reasoning for final decision
5. VERIFICATION statement confirming logic is correct

Format:
BUY: [YES or NO]
PROBABILITY: [0.0 to 1.0]
CONFIDENCE: [0.0 to 1.0]
REASONING: [synthesis of prediction and critique]
VERIFICATION: I am buying [outcome] because I think it has [probability]% chance of happening, which is more likely than the alternative.
"""

        response = self.client.chat.completions.create(
            model=self.model,  # Use configured model (grok-beta or gpt-4)
            messages=[
                {"role": "system", "content": "You are a careful decision maker who verifies logic."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=800
        )

        content = response.choices[0].message.content

        outcome_to_buy = self._extract_field(content, "BUY")

        # Robust parsing for micro-markets
        try:
            prob_str = self._extract_field(content, "PROBABILITY", "0.5")
            # Remove brackets if present
            prob_str = prob_str.strip("[]")
            probability = float(prob_str)
        except (ValueError, AttributeError):
            probability = 0.5

        try:
            conf_str = self._extract_field(content, "CONFIDENCE", "0.5")
            conf_str = conf_str.strip("[]")
            confidence = float(conf_str)
        except (ValueError, AttributeError):
            confidence = 0.5

        reasoning = self._extract_field(content, "REASONING", "")
        verification = self._extract_field(content, "VERIFICATION", "")

        return FinalDecision(
            outcome_to_buy=outcome_to_buy.strip().upper(),
            probability=probability,
            confidence=confidence,
            reasoning=reasoning,
            verification=verification
        )

    def verify_decision(
        self,
        decision: FinalDecision,
        prediction: Prediction
    ) -> Tuple[bool, str]:
        """
        Final verification: Catch logical errors

        Returns: (is_valid, error_message)
        """

        # Check 1: Did we buy the more likely outcome?
        if prediction.probability > 0.5:
            expected_buy = prediction.outcome
        else:
            # If prediction says YES is <50%, we should buy NO
            expected_buy = "NO" if prediction.outcome == "YES" else "YES"

        if decision.outcome_to_buy != expected_buy:
            return False, f"ERROR: Prediction says {prediction.outcome} at {prediction.probability:.0%}, but decision is to buy {decision.outcome_to_buy}. This is backwards!"

        # Check 2: Is probability in valid range?
        if not (0.0 <= decision.probability <= 1.0):
            return False, f"ERROR: Probability {decision.probability} is out of range [0, 1]"

        # Check 3: Is confidence reasonable?
        if not (0.0 <= decision.confidence <= 1.0):
            return False, f"ERROR: Confidence {decision.confidence} is out of range [0, 1]"

        return True, "Verification passed"

    def full_reasoning_pipeline(
        self,
        question: str,
        description: str,
        market_data: Dict,
        social_data: Optional[Dict] = None
    ) -> Dict:
        """
        Run full multi-agent reasoning pipeline

        Returns complete analysis with all agent outputs
        """

        # Step 1: Prediction
        prediction = self.predict(question, description, market_data, social_data)

        # Step 2: Critique
        critique = self.critique(question, prediction)

        # Step 3: Synthesis
        decision = self.synthesize(question, prediction, critique)

        # Step 4: Verification
        is_valid, verification_message = self.verify_decision(decision, prediction)

        return {
            "prediction": prediction,
            "critique": critique,
            "decision": decision,
            "verification": {
                "passed": is_valid,
                "message": verification_message
            },
            "final_outcome_to_buy": decision.outcome_to_buy if is_valid else None,
            "final_probability": decision.probability if is_valid else None,
            "final_confidence": decision.confidence if is_valid else None
        }

    def _extract_field(self, content: str, field: str, default: str = "") -> str:
        """Extract field from formatted response"""
        lines = content.split("\n")
        for line in lines:
            if line.startswith(f"{field}:"):
                return line.split(":", 1)[1].strip()
        return default
