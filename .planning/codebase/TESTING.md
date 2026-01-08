# Testing Patterns

**Analysis Date:** 2026-01-08

## Test Framework

**Runner:**
- pytest 8.3.2
- unittest (minimal use, legacy tests only)

**Assertion Library:**
- pytest built-in `assert`
- unittest assertions (`self.assertEqual`, etc.) in legacy tests

**Run Commands:**
```bash
pytest                                  # Run all tests
pytest -v                               # Verbose mode
pytest tests/test_copytrader.py         # Single file
pytest -k "test_risk"                   # Pattern match
python -m unittest discover             # Legacy unittest runner
```

## Test File Organization

**Location:**
- `tests/` directory at project root
- Co-located with source: No (all tests in central directory)

**Naming:**
- Unit tests: `test_{module}.py` (e.g., `test_copytrader.py`)
- Integration tests: `test_{module}_integration.py`
- Parity tests: `test_parity.py`

**Structure:**
```
tests/
├── test.py                          # Placeholder unittest tests
├── test_copytrader.py               # Core 20-test suite
├── test_copytrader_integration.py   # Integration tests (empty)
├── test_copytrader_legacy.py        # Legacy schema tests
├── test_parity.py                   # Executor equivalence tests
└── mocks/                           # Mock objects
```

## Test Structure

**Suite Organization:**
```python
import pytest
from datetime import datetime
from decimal import Decimal

@pytest.fixture
def temp_db():
    """Temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield CopyTraderDB(str(db_path))

@pytest.fixture
def risk_kernel():
    """Standard risk kernel with v1 limits."""
    return RiskKernel(
        starting_capital=Decimal("1000.0"),
        daily_stop_pct=Decimal("-5.0"),
        hard_kill_pct=Decimal("-20.0"),
        per_trade_cap_pct=Decimal("3.0"),
        max_positions=3,
    )

class TestTradeIntentSchema:
    """Test TradeIntent schema validation"""

    def test_valid_buy_intent(self):
        """Test creating a valid BUY intent"""
        intent = TradeIntent(
            source_trader="0x" + "a" * 40,
            market_id="test_market_123",
            outcome=Outcome.YES,
            side=Side.BUY,
            size_usdc=50.0,
        )

        assert intent.source_trader == "0x" + "a" * 40
        assert intent.side == Side.BUY
        assert intent.size_usdc == 50.0
```

**Patterns:**
- `pytest.fixture` for setup (replaces beforeEach/afterEach)
- Test classes group related tests (TestTradeIntentSchema, TestRiskKernel)
- Descriptive test names: `test_valid_buy_intent`, `test_reject_stale_intent`
- Docstrings explain test purpose

## Mocking

**Framework:**
- pytest built-in mocking capabilities
- unittest.mock (not detected in current tests)

**Patterns:**
```python
# Fixture-based mocking
@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield CopyTraderDB(str(db_path))

# No module mocking detected yet
```

**What to Mock:**
- Database: Temporary SQLite database via fixture
- External APIs: Not currently mocked (missing tests)
- Time: datetime objects in tests (no freeze_time detected)

**What NOT to Mock:**
- RiskKernel: Pure function, no mocking needed
- Pydantic models: Data validation, test directly
- Internal business logic: Test actual implementation

## Fixtures and Factories

**Test Data:**
```python
# Fixture pattern
@pytest.fixture
def risk_kernel():
    return RiskKernel(
        starting_capital=Decimal("1000.0"),
        daily_stop_pct=Decimal("-5.0"),
        hard_kill_pct=Decimal("-20.0"),
        per_trade_cap_pct=Decimal("3.0"),
        max_positions=3,
        anomalous_loss_pct=Decimal("-5.0"),
    )

# Factory pattern (inline)
def create_test_intent():
    return TradeIntent(
        source_trader="0x" + "a" * 40,
        market_id="test_market",
        outcome=Outcome.YES,
        side=Side.BUY,
        size_usdc=50.0,
    )
```

**Location:**
- Fixtures: Defined at top of test file
- Factories: Inline helper functions (no separate factories/ directory)
- Shared fixtures: Not detected (no conftest.py)

## Coverage

**Requirements:**
- No enforced coverage target
- Coverage tracked for awareness only
- Focus: Critical paths (risk kernel, intent validation, position tracking)

**Configuration:**
- Tool: pytest-cov (not detected in requirements.txt)
- No pytest.ini or setup.cfg configuration

**View Coverage:**
```bash
# Not currently configured
pytest --cov=agents --cov-report=html
open htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Scope: Single function/class in isolation
- Mocking: Database via temporary fixture
- Speed: Fast (<1s per test)
- Examples: `test_copytrader.py` - intent validation, risk kernel

**Integration Tests:**
- Scope: Multiple modules together
- Mocking: External APIs, database
- Examples: `test_copytrader_integration.py` (currently empty)

**Parity/Equivalence Tests:**
- Scope: Interface compliance between implementations
- Purpose: Verify Mock and Live executors behave identically
- Examples: `test_parity.py`
```python
def test_mock_executor_interface_compliance():
    """
    Parity Test 1: Verify MockExecutor implements ExecutorAdapter correctly.

    Category: MUST Match
    Falsifier: Interface violation
    """
    executor = MockExecutor(should_fail=False)
    assert isinstance(executor, ExecutorAdapter)
    assert hasattr(executor, "execute_market_order")
```

**E2E Tests:**
- Not detected - No end-to-end tests

## Common Patterns

**Async Testing:**
```python
# Not detected - no async tests yet
```

**Error Testing:**
```python
def test_invalid_address(self):
    """Test that invalid Ethereum addresses are rejected"""
    with pytest.raises(ValueError, match="must start with 0x"):
        TradeIntent(
            source_trader="invalid_address",
            market_id="test_market",
            outcome=Outcome.YES,
            side=Side.BUY,
            size_usdc=50.0,
        )

def test_missing_size(self):
    """Test that intents without size are rejected"""
    with pytest.raises(ValueError, match="Must specify either"):
        TradeIntent(
            source_trader="0x" + "a" * 40,
            market_id="test_market",
            outcome=Outcome.YES,
            side=Side.BUY,
        )
```

**Validation Testing:**
```python
def test_reject_stale_intent(intent_validator):
    """Test 1: Intent older than 10s rejected."""
    old_time = datetime.now(timezone.utc) - timedelta(seconds=11)
    intent = TradeIntent(
        source_trader="0x" + "a" * 40,
        market_id="test_market",
        outcome=Outcome.YES,
        side=Side.BUY,
        size_usdc=50.0,
        timestamp=old_time,
    )

    result = intent_validator.validate(intent, allowlist=["test_market"], current_positions_count=0)
    assert not result.valid
    assert result.rejection_reason == IntentRejectionReason.STALE
```

**Snapshot Testing:**
- Not used

## Test Organization Strategy

**20-Test Minimum Suite** (documented in `tests/test_copytrader.py`):
1. Intent validation (5 tests)
   - Staleness check
   - Allowlist validation
   - Position limit check
   - Side validation
   - Size validation
2. Risk kernel (7 tests)
   - Daily stop loss
   - Hard kill switch
   - Per-trade cap
   - Position limits
   - Anomalous loss detection
3. Position tracking (4 tests)
   - Record trade
   - Get open positions
   - Calculate PnL
   - Clear position
4. Execution flow (3 tests)
   - Mock execution
   - Live execution interface
   - Error handling
5. Alerts (1 test)
   - Discord notification

**Fail-Closed Philosophy:**
- Tests verify rejection logic for invalid states
- Tests verify acceptance logic for valid states
- Example: `test_reject_stale_intent()` ensures stale intents are rejected

**Parity Criteria:**
- MUST Match: Interface compliance, zero tolerance
- Mock and Live executors must maintain semantic equivalence

## CI/CD Integration

**GitHub Actions:**
- Workflow: `.github/workflows/python-app.yml`
- Triggers: Push to main, pull requests
- Steps:
  1. Checkout code
  2. Set up Python 3.9
  3. Install dependencies (pytest, black, requirements.txt)
  4. Lint with black
  5. Test with unittest discover (legacy)

**Docker:**
- Workflow: `.github/workflows/docker-image.yml`
- Validates Docker build on push/PR

---

*Testing analysis: 2026-01-08*
*Update when test patterns change*
