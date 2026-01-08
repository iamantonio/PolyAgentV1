# Coding Conventions

**Analysis Date:** 2026-01-08

## Naming Patterns

**Files:**
- Snake case for all files: `risk_kernel.py`, `position_tracker.py`, `polymarket.py`
- Test files: `test_*.py` pattern (`test_copytrader.py`, `test_parity.py`)
- No special suffix for modules

**Functions:**
- Snake case for all functions: `get_llm_response()`, `execute_market_order()`, `validate_side()`
- Async functions: No special prefix (same as sync)
- Private methods: Leading underscore `_init_db()`, `_init_api_keys()`

**Variables:**
- Snake case: `market_data`, `total_tokens`, `user_input`
- Constants: UPPER_SNAKE_CASE (`SCHEMA_VERSION`, `MAX_INT`)
- No underscore prefix for private attributes (Python convention via name mangling)

**Types:**
- Classes: PascalCase (`Polymarket`, `RiskKernel`, `TradeIntent`, `PositionTracker`)
- Pydantic models: PascalCase (`SimpleMarket`, `PolymarketEvent`, `ClobReward`)
- Enums: PascalCase for name, UPPER_CASE for values (`Side.BUY`, `Outcome.YES`)
- No interface prefix (no `ITrader`, just `Trader`)

## Code Style

**Formatting:**
- Tool: Black 24.4.2 (enforced via `.pre-commit-config.yaml`)
- Line length: 88 characters (Black default)
- Quotes: Double quotes preferred by Black (though single quotes appear in legacy code)
- Semicolons: Not used (Python convention)
- Indentation: 4 spaces (Python standard)

**Linting:**
- Tool: Black only (no pylint, flake8, or mypy detected)
- Pre-commit hook: Required for contributions (`pre-commit install`)
- CI enforcement: GitHub Actions runs `black .` on push/PR

## Import Organization

**Order:**
1. Standard library imports (`import os`, `from datetime import datetime`)
2. Third-party packages (`from web3 import Web3`, `import httpx`)
3. Local modules (`from agents.utils.objects import Trade`)
4. Type imports (no explicit `from typing import` separation)

**Grouping:**
- No blank lines between groups (not enforced)
- Alphabetical within groups (not consistently enforced)

**Path Aliases:**
- None detected - all imports use relative or absolute paths

## Error Handling

**Patterns:**
- Mixed strategy: Some functions raise exceptions, others return None
- **ANTI-PATTERN**: Bare `except:` clauses in `agents/application/trade.py` (swallow all errors)
- **ANTI-PATTERN**: Generic `except Exception as e:` with only `print(e)`
- Validation errors: Pydantic raises `ValidationError`

**Error Types:**
- Custom errors: Not detected (uses standard library exceptions)
- Raise on invalid input: Pydantic models validate on instantiation
- Return None: Some API methods return None on failure (implicit)

**Logging:**
- **ISSUE**: Print statements used instead of logging module (25+ instances)
- No structured logging
- Example: `print(f"Error {e} \\n \\n Retrying")`

## Logging

**Framework:**
- **CURRENT**: `print()` statements throughout
- **NEEDED**: Python `logging` module (not currently used)

**Patterns:**
- Debug prints: `print("1")`, `print(f'total tokens {total_tokens}...')`
- Error prints: `print(f"Error {e}")`
- Info prints: `print(len(res.json()))`

## Comments

**When to Comment:**
- Module docstrings: Triple-quoted at top of file
- Function docstrings: Google-style with Args/Returns
- Inline comments: Minimal (self-documenting code preferred)
- TODO comments: Present but untracked (e.g., "TODO: Integrate with Polymarket API")

**JSDoc/Docstrings:**
- Format: Google-style (Args, Returns, Raises sections)
- Required for: Public APIs, complex functions
- Optional for: Internal helpers, simple methods
- Example:
  ```python
  def validate(self, intent: TradeIntent) -> IntentValidationResult:
      \"\"\"
      Validate intent against all rules.

      Args:
          intent: Trade intent to validate
          allowlist: List of allowed market IDs

      Returns:
          IntentValidationResult with validation status
      \"\"\"
  ```

**TODO Comments:**
- Format: `# TODO: description` (no username or issue link)
- Examples:
  - "TODO: Integrate with Polymarket API to fetch market category"
  - "TODO: Add proper connectivity check"

## Function Design

**Size:**
- Target: Keep under 100 lines
- Reality: Some functions exceed 200 lines (`polymarket.py`)
- Extract helpers for complex logic (inconsistently applied)

**Parameters:**
- No explicit limit (some functions have 5+ parameters)
- Type hints: Used consistently
- Default values: Used appropriately
- Destructuring: Not used (Python doesn't have it)

**Return Values:**
- Explicit returns preferred
- Return early for guard clauses (inconsistently applied)
- Return None: Implicit in some cases (should be explicit)

## Module Design

**Exports:**
- All classes/functions are implicitly public (no `__all__`)
- No default exports (Python doesn't have them)
- Import from module: `from agents.polymarket import Polymarket`

**Barrel Files:**
- Not used (no `__init__.py` re-exports detected)
- Direct imports: `from agents.copytrader.risk_kernel import RiskKernel`

## Type Annotations

**Usage:**
- Consistent type hints on function signatures
- Return types: Present but not comprehensive
- Pydantic models: Full type safety via validation
- Optional types: `Optional[str]`, `Optional[bool]`
- List types: Mix of `List[str]` and `list[str]` (Python 3.9+)
- Union types: `Union[int, float]` where needed

**Examples:**
```python
def get_llm_response(self, user_input: str) -> str:
    ...

def validate(
    self,
    intent: TradeIntent,
    allowlist: List[str],
    current_positions_count: int,
) -> IntentValidationResult:
    ...
```

## Patterns

**Enums for Fixed Values:**
```python
class IntentRejectionReason(Enum):
    STALE = "stale"
    NOT_ON_ALLOWLIST = "not_on_allowlist"
    POSITION_LIMIT_REACHED = "position_limit_reached"
```

**Dataclasses for Immutable Data:**
```python
@dataclass
class IntentValidationResult:
    valid: bool
    intent: Optional[TradeIntent]
    rejection_reason: Optional[IntentRejectionReason]
```

**Pydantic Models for Validation:**
```python
class TradeIntent(BaseModel):
    source_trader: str
    market_id: str
    outcome: Outcome
    side: Side
    size_usdc: Optional[float] = None

    @model_validator(mode='after')
    def validate_size(self):
        # Validation logic
        return self
```

**Config Objects:**
```python
@dataclass
class AlertConfig:
    enabled: bool = True
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
```

---

*Convention analysis: 2026-01-08*
*Update when patterns change*
