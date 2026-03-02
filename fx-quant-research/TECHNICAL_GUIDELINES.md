# FX Quant Signal Research – Technical Guidelines

This document specifies the technical implementation guidelines and design decisions for the FX Quantitative Research Framework.

---

## 1️⃣ Data Location & Loading

### CSV Data Management

- **Default CSV location**: `data/raw/`
- **Path configuration**: Absolute path stored in `config/config.yaml` under key `data.raw_path`
- **Dynamic alternative**: CLI argument to specify CSV path at runtime
- **Policy**: No downloading; rely solely on CSV provided by user

### Missing Data Handling

- **Default policy**: Leave as NaN. Do not forward-fill unless explicitly requested.
- **Rolling calculations**: Use `min_periods` parameter to handle NaNs naturally
- **Explicit imputation**: Only through `forensics.py` layer with full audit trail

### CSV Format Requirements

```csv
timestamp,open,high,low,close,volume,spread
2020-01-02 00:00:00,1.1200,1.1250,1.1180,1.1220,150000,0.0001
```

- **Required columns**: timestamp, open, high, low, close, volume
- **Optional columns**: spread (bid-ask spread in price units)
- **Timestamp format**: Any pandas-parseable format, converted to UTC internally
- **Data quality**: No duplicates, monotonic time series

---

## 2️⃣ Backtest Framework

### Implementation Approach

**Decision**: Custom vectorized, Pandas-native implementation

**Rationale**:

- **Zipline**: End-of-life / too heavy for FX use case
- **Backtrader**: Slow for large datasets
- **vectorbt**: Excellent but adds extra dependency

### Core Capabilities

1. **Full control over signal lag handling**
   - Mandatory 1-bar execution lag via `.shift(1)`
   - No lookahead bias enforcement

2. **Custom cost application**
   - Multi-component transaction costs
   - Configurable by pair tier

3. **Reproducibility**
   - Seed management for all stochastic components
   - Experiment logging with full environment capture

### Key Components

```python
# Backtest output includes:
- equity_curve        # Daily equity values
- drawdown           # Running drawdown series
- positions          # Position history (lagged)
- trades             # Trade volume per bar
- returns            # Daily returns (gross & net)
- cost_breakdown     # Component cost attribution
- metrics            # Performance statistics
```

### Performance Metrics

- **Returns**: Total return, annualized return (CAGR)
- **Risk-adjusted**: Sharpe ratio, Sortino ratio, Calmar ratio
- **Risk**: Maximum drawdown, volatility
- **Activity**: Turnover, total trades, win rate
- **Distribution**: Skewness, kurtosis

### Critical Implementation Detail

**1-Bar Execution Lag** (enforced in `engine.py:96-97`):

```python
# Signal at time t executes at time t+1
positions = signals.shift(execution_lag).fillna(0)

# Returns calculated using position set previous bar
gross_returns = positions.shift(1) * returns
```

---

## 3️⃣ Hidden Markov Model (HMM)

### Primary Implementation

**Library**: `hmmlearn` (`hmmlearn.hmm.GaussianHMM`)

**Configuration**:

```yaml
regime:
  n_states: 3 # low / medium / high volatility
  covariance_type: "full" # Capture feature correlations
  max_iter: 100 # EM algorithm iterations
  features:
    - "returns"
    - "volatility"
    - "volume_zscore"
```

### Fallback: Gaussian Mixture Model

**Library**: `sklearn.mixture.GaussianMixture`

**Use case**: Non-temporal clustering when HMM assumptions don't hold

### Outputs

1. **Regime labels**: State assignment per bar (0 to n_states-1)
2. **Regime probabilities**: Probability matrix (n_bars × n_states)
3. **Transition matrix**: State persistence and switching dynamics
4. **Regime statistics**:
   - Mean duration per state
   - Empirical transition frequencies
   - Stability (diagonal elements of transition matrix)
5. **Performance by regime**: Sharpe, mean return, volatility per state

### Feature Requirements

- **Stationarity**: All features must be stationary (use ADF + KPSS tests)
- **Scaling**: Z-score normalization recommended
- **Common features**: Returns, log-volatility, normalized volume

---

## 4️⃣ Transaction Costs

### Spread Costs

**Configuration** (in basis points):

```yaml
costs:
  spread_bps:
    majors: 1.5 # EURUSD, USDJPY, GBPUSD, USDCHF
    minors: 3.0 # EURGBP, EURJPY, AUDUSD, NZDUSD
    exotics: 10.0 # USDTRY, USDZAR, USDBRL
```

**Formula**:

```
spread_cost = 0.5 × (spread_bps / 10000) × price × |size|
```

### Slippage Model

**Square-root model** (empirical FX microstructure):

```
slippage = volatility × √(|size| / volume) × price × coefficient
```

**Default coefficient**: 0.1 (configurable)

### Market Impact

**Power-law model**:

```
impact = price × (|size| / daily_volume)^exponent × coefficient
```

**Parameters**:

- **Exponent**: 0.5 (square-root law from academic literature)
- **Coefficient**: 0.05 (configurable)

### Swap/Rollover Costs

**Policy**: Optional; applied only if CSV exists under `data/swap_rates/`

**Triple Wednesday Rule**: 3× daily swap on Wednesday to account for weekend rollover

**Formula**:

```
daily_swap = (swap_rate / 360) × position × price
multiplier = 3 if weekday == Wednesday else 1
```

---

## 5️⃣ Testing Strategy

### Property-Based Testing (Hypothesis)

**Critical test**: Backtest lag logic (`tests/unit/test_backtest.py`)

```python
@given(
    n_bars=st.integers(min_value=20, max_value=100),
    signal_changes=st.lists(st.tuples(...))
)
def test_lag_enforcement_property(n_bars, signal_changes):
    """
    PROPERTY: For ANY signal pattern,
    position[t] == signal[t-1] for all t > 0
    """
    # Generate arbitrary signals
    # Run backtest
    # Assert: positions.iloc[i] == signals.iloc[i-1]
```

**Why hypothesis**: Validates lag enforcement across infinite signal patterns, not just handcrafted examples.

### Standard Unit Tests (pytest)

**Components tested**:

- Data loader: CSV parsing, timezone handling, duplicate detection
- Validator: OHLC logic, spike detection (z-score + MAD), missing bars
- Cost model: Spread/slippage/impact formulas, swap calculation
- Feature engineering: Returns, volatility estimators, stationarity tests

### Integration Tests

**End-to-end workflow**:

1. Load fixture CSV
2. Generate signals (e.g., SMA crossover)
3. Run backtest with costs
4. Verify reasonable metrics
5. **Reproducibility test**: Run twice with same seed, assert exact match

### Mocking Strategy

**I/O testing**: Mock file reads and heavy data operations in unit tests

**Example**:

```python
@pytest.fixture
def sample_csv_file(tmp_path):
    csv_path = tmp_path / "test_data.csv"
    df.to_csv(csv_path)
    return csv_path
```

---

## 6️⃣ Type System & Config Validation

### Interfaces: Protocol-Based

**Duck-typed type safety** via `typing.Protocol`:

```python
from typing import Protocol, Literal

class TransactionCostModel(Protocol):
    def calculate_cost(
        self,
        price: float,
        size: float,
        side: Literal['buy', 'sell'],
        timestamp: pd.Timestamp,
        **context
    ) -> float:
        ...
```

**Benefits**:

- No inheritance required
- Multiple implementations (FXCostModel, MockCostModel, etc.)
- Static type checking validates signature

### Runtime Validation: Pydantic

**Configuration models** (`utils/environment.py`):

```python
from pydantic import BaseModel, Field

class CostConfig(BaseModel):
    spread_bps_major: float = Field(gt=0, le=100)
    slippage_coefficient: float = Field(gt=0)
    market_impact_exponent: float = Field(ge=0, le=1)
```

**Benefits**:

- Runtime validation
- Automatic type coercion
- Clear error messages

### Array Typing

**Use `numpy.typing.NDArray`**:

```python
from numpy.typing import NDArray
import numpy as np

def calculate_returns(prices: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.diff(np.log(prices))
```

### Documentation Requirements

**All modules must include**:

1. Type annotations on all functions
2. Docstrings following Google style:
   ```python
   def function(arg1: type1, arg2: type2) -> return_type:
       """One-line summary.

       Args:
           arg1: Description
           arg2: Description

       Returns:
           Description

       Raises:
           ValueError: When...

       Examples:
           >>> function(1, 2)
           3
       """
   ```

---

## 7️⃣ Missing Data & Forward-Filling Policy

### Default Policy

**Do not forward-fill**; missing bars remain `NaN`.

**Rationale**:

- Explicit > implicit
- Avoids lookahead bias from filling future data
- Forces conscious imputation decisions

### Rolling Function Guidelines

**Use `min_periods` parameter**:

```python
# ✅ Correct: Handles NaNs naturally
df['sma_20'] = df['close'].rolling(20, min_periods=10).mean()

# ❌ Incorrect: Forward-fills implicitly
df['close_filled'] = df['close'].fillna(method='ffill')
df['sma_20'] = df['close_filled'].rolling(20).mean()
```

**Common patterns**:

```python
# Volatility with incomplete windows
vol = returns.rolling(20, min_periods=10).std()

# EWM always works (doesn't require min_periods)
ema = prices.ewm(span=20).mean()
```

### Explicit Imputation

**Only through `forensics.py` layer**:

```python
from src.data.forensics import DataForensics

forensics = DataForensics()

# Option 1: Analyze missing data
report = forensics.generate_report(df, pair='EURUSD')
# Reports: missing bars, gaps, quality score

# Option 2: Explicit imputation with audit trail
df_imputed = forensics.impute_missing_bars(
    df,
    method='linear',
    log_to='reports/imputation_audit.json'
)
```

**Audit trail includes**:

- Timestamps of imputed bars
- Method used
- Pre/post quality scores
- SHA256 hash of original data

### Business Day Handling

**FX market assumptions**:

- Trading: Monday 00:00 UTC to Friday 23:59 UTC
- Weekends: Expected gaps, not missing data
- Holidays: Currency-specific (e.g., USD holidays, JPY holidays)

**Validation**:

```python
# Detector uses business day calendar
validator.detect_missing_bars(df, freq='D')
# Ignores Saturday/Sunday gaps
```

---

## 8️⃣ Reproducibility Guidelines

### Seed Management

**Set before all stochastic operations**:

```python
from src.backtest.seed_manager import set_global_seed, get_random_state

# Global seed (random, numpy)
set_global_seed(42)

# Scoped seed for sklearn/hmmlearn
rs = get_random_state(42)
model = GaussianHMM(n_components=3, random_state=rs)
```

### Experiment Logging

**Log every backtest** (`utils/environment.py`):

```python
from src.utils.environment import log_experiment, capture_environment

env = capture_environment()  # Python version, library versions, timestamp

exp_id = log_experiment(
    config=config_dict,
    environment=env,
    results=backtest_metrics,
    data_files={'eurusd': 'data/raw/eurusd.csv'}
)
# Writes to logs/experiment_log.json with UUID
```

**Logged information**:

- UUID (for retrieval)
- Full config snapshot
- Data file hashes (SHA256)
- Python + library versions
- Random seeds
- Result metrics
- Timestamp

### Verification

**Compare two experiment runs**:

```python
from src.utils.environment import verify_reproducibility

match = verify_reproducibility(exp_id_1, exp_id_2, tolerance=1e-10)
# Returns: True if equity curves match within tolerance
```

---

## 9️⃣ Performance Optimization

### Vectorization

**Prefer vectorized pandas/numpy operations** over loops:

```python
# ✅ Vectorized
returns = np.log(prices / prices.shift(1))

# ❌ Loop-based
returns = []
for i in range(1, len(prices)):
    returns.append(np.log(prices[i] / prices[i-1]))
```

### Memory Management

**For large datasets**:

1. Use parquet instead of CSV (faster I/O)
2. Process data in chunks
3. Drop unnecessary columns after feature generation
4. Use categorical dtypes for regime labels

```python
# Categorical for regimes saves memory
df['regime'] = df['regime'].astype('category')

# Check memory usage
df.memory_usage(deep=True)
```

### Profiling

**Identify bottlenecks**:

```python
# Time critical sections
import time
start = time.perf_counter()
result = backtest.run(...)
elapsed = time.perf_counter() - start
print(f"Backtest took {elapsed:.2f}s")

# Or use cProfile for detailed profiling
python -m cProfile -o output.prof script.py
```

---

## 🔟 Extension Points

### Custom Cost Models

Implement `TransactionCostModel` protocol:

```python
class MyCustomCostModel:
    def calculate_cost(self, price, size, side, timestamp, **ctx):
        # Your custom logic
        return cost

    def total_cost(self, price, size, side, timestamp, **ctx):
        # Return breakdown
        return {
            'total_cost': ...,
            'total_cost_bps': ...,
            'breakdown': {...}
        }
```

### Alternative Regime Detectors

Extend base interface:

```python
from src.features.regime_detector import GMMRegimeDetector

class MyRegimeDetector:
    def fit(self, features: pd.DataFrame):
        # Train on features
        pass

    def predict(self, features: pd.DataFrame) -> pd.Series:
        # Return state labels
        pass

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        # Return probability matrix
        pass
```

### Custom Features

Extend `FeatureEngineering` class:

```python
from src.features.library import FeatureEngineering

class MyFeatures(FeatureEngineering):
    def add_custom_indicator(self, df, param=20):
        df['my_indicator'] = ...  # Your calculation
        return df
```

---

## 📋 Compliance Checklist

Before committing code, verify:

- [ ] All functions have type annotations
- [ ] Docstrings follow Google style
- [ ] No forward-filling unless audited via forensics
- [ ] Rolling functions use `min_periods`
- [ ] Backtest enforces 1-bar execution lag
- [ ] Transaction costs configurable via YAML
- [ ] Tests include property-based tests for lag logic
- [ ] Experiment logging captures full environment
- [ ] Random seeds set before stochastic operations
- [ ] No hardcoded paths (use config)

---

## 📚 References

### Academic Literature

1. **Market Microstructure**:
   - Almgren & Chriss (2000) - Optimal execution with market impact
   - Bouchaud et al. (2018) - Square-root law of market impact

2. **Regime Detection**:
   - Hamilton (1989) - Markov-switching models
   - Ang & Bekaert (2002) - Regime switches in interest rates

3. **Volatility Estimation**:
   - Parkinson (1980) - High-low volatility estimator
   - Garman & Klass (1980) - OHLC volatility estimator

### Implementation References

- **pandas**: https://pandas.pydata.org/docs/
- **hmmlearn**: https://hmmlearn.readthedocs.io/
- **hypothesis**: https://hypothesis.readthedocs.io/
- **pydantic**: https://docs.pydantic.dev/

---

## 🔄 Version History

| Version | Date       | Changes                      |
| ------- | ---------- | ---------------------------- |
| 1.0     | 2026-03-02 | Initial technical guidelines |

---

**Maintained by**: FX Quant Research Team  
**Last updated**: 2026-03-02
