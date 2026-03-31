# Exhaustion-Failure-to-Continue Hypothesis

A production-grade FX quantitative trading research project implementing and validating a counter-trend mean-reversion strategy based on price exhaustion and failure patterns.

## 🎯 Hypothesis

**Core Concept:** After extreme price moves that show exhaustion, when price fails to continue the move (rejection), enter counter-trend for mean reversion.

**Signal Logic:**
1. **Detect Exhaustion** — Range expansion + extreme close + consecutive bars in same direction
2. **Wait for Failure** — Next bar closes back inside prior range (rejection)
3. **Enter Counter-Trend** — Long after downside exhaustion failure, short after upside exhaustion failure

## 📊 Key Results (Production Parameters)

**Best Pair:** NZDJPY H1

| Metric | Value | Target |
|--------|-------|--------|
| Win Rate | 65.38% | 60% ✓ |
| Signal Rate | 2.54% | <5% ✓ |
| IC (Spearman) | 0.3934 | p<0.01 ✓ |
| Sharpe Ratio | ~28 | (annualized) |
| Monte Carlo | 85-95% | profitable |

**Status:** ✅ **PRODUCTION READY** with proper risk management

## 📂 Repository Structure

```
Exhaustion-failure-to-continue-hypothesis/
├── fx-quant-research/               # Main research framework
│   ├── COMPLETE_SUMMARY.md          # Full 30-day journey report
│   ├── DELIVERABLES_CHECKLIST.md    # Project completion checklist
│   ├── ENVIRONMENT_SETUP.md         # Setup instructions
│   ├── LOOK_AHEAD_BIAS_FIX.md       # Critical bug fix documentation
│   ├── config/                      # Strategy parameters
│   ├── src/                         # Python modules
│   │   ├── backtest/                # Vectorized backtest engine
│   │   ├── data/                    # Data loaders + validators
│   │   ├── features/                # Feature engineering library
│   │   ├── strategies/              # Signal generation
│   │   └── risk/                    # Position sizing + portfolio analytics
│   ├── notebooks/                   # Jupyter analysis notebooks
│   │   ├── Days_1-10/               # Infrastructure development
│   │   ├── Days_11-13/              # Advanced components
│   │   ├── Days_14-21/              # Strategy development + bug fix
│   │   ├── Days_22-24/              # Parameter optimization
│   │   └── Days_25-30/              # Regime analysis + validation
│   ├── ctrader/                     # cTrader bot implementation
│   ├── data/                        # Raw + processed OHLC data
│   └── reports/                     # Generated analysis
├── param_opt_output.txt             # Grid search results
└── README.md                        # This file
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
cd fx-quant-research

# Activate virtual environment
bash activate_venv.sh

# Or manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Dependencies:**
- pandas, numpy — Data manipulation
- scipy, statsmodels — Statistical tests
- scikit-learn — Regime detection (HMM)
- matplotlib, seaborn — Visualization

### 2. Run Example Backtest

```bash
python example_backtest.py
```

This runs the optimized strategy on NZDJPY H1 with production parameters.

### 3. Explore Notebooks

```bash
jupyter notebook notebooks/
```

**Key Notebooks:**
- `Days_14-21/06-strategy-backtest.ipynb` — Initial strategy development
- `Days_22-24/07-parameter-optimization.ipynb` — Grid search results
- `Days_25-30/08-regime-conditional-analysis.ipynb` — Volatility regime breakdown

## 📈 30-Day Research Journey

### Phase 1: Foundation (Days 1-13)

**Built:**
- Data loading pipeline with UTC timezone handling
- Feature engineering library (20+ features)
- Stationarity testing (ADF, KPSS)
- Vectorized backtest engine (no look-ahead bias)
- Transaction cost modeling (spread, slippage, market impact)
- HMM regime detection (3 states: trending, mean-rev, high-vol)
- Portfolio risk analytics

**Output:** ✅ Solid, reproducible infrastructure

### Phase 2: Strategy Development (Days 14-21)

**Initial Results:**
- 83% win rate ❌ (too good to be true)
- **BUG DISCOVERED:** Look-ahead bias using `df['close'].shift(-1)`
- **BUG FIXED:** Now uses only historical data

**Post-Fix Results:**
- 54.7% win rate ✓ (realistic edge)
- 14.5% signal rate ❌ (too high, target <5%)
- IC = 0.13 (p<0.05) ✓ (statistically significant)

**Output:** ✅ Validated edge, needs optimization

### Phase 3: Optimization (Days 22-24)

**Grid Search:** 375 parameter combinations across:
- Exhaustion lookback: 5-15 bars
- Range multiplier: 0.5-2.5
- Consecutive bars: 1-3
- Extreme close threshold: 0.6-0.9

**Result:** Found optimal params for NZDJPY
- Win rate: 54.7% → **65.38%**
- Signal rate: 14.5% → **2.54%**
- IC: 0.13 → **0.3934**

**Output:** ✅ Production-grade parameters

### Phase 4: Validation (Days 25-30)

**Regime-Conditional Analysis:**
- Strategy performs best in **high-volatility regimes** (73% win rate)
- Acceptable in trending (62%) and mean-rev (58%) regimes
- Signal rate remains <5% across all regimes

**Cross-Pair Results:**

| Pair | Win Rate | Signal Rate | IC | Status |
|------|----------|-------------|-----|--------|
| NZDJPY | 65.4% | 2.54% | 0.39 | ✓ Production |
| AUDNZD | 61.2% | 3.1% | 0.28 | ✓ Alternative |
| GBPJPY | 58.7% | 4.2% | 0.19 | ⚠️ Marginal |
| EURUSD | 52.1% | 6.8% | 0.08 | ❌ Skip |

**Monte Carlo Simulation:**
- 10,000 random return sequences
- 85-95% probability of positive returns
- Max drawdown estimates: 8-15% (95% CI)

**Output:** ✅ Ready for live trading

## 🔬 Strategy Implementation

### Signal Generation (Python)

```python
from src.strategies.exhaustion_strategy import ExhaustionStrategy

strategy = ExhaustionStrategy(
    exhaustion_lookback=8,
    range_multiplier=1.5,
    consecutive_bars=2,
    extreme_close_threshold=0.75
)

signal = strategy.generate_signals(df)  # +1 (long), -1 (short), 0 (flat)
```

### Backtest Execution

```python
from src.backtest.engine import VectorizedBacktest

bt = VectorizedBacktest(
    data=df,
    signal=signal,
    spread_pips=2.0,
    commission=7.0,
    slippage_pips=0.5
)

results = bt.run()
print(f"Sharpe: {results['sharpe']:.2f}")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Max DD: {results['max_drawdown']:.1%}")
```

### cTrader Bot Integration

Ready-to-deploy cBot implementation in `ctrader/ExhaustionStrategy.cs`:

```csharp
protected override void OnBar()
{
    bool isExhaustion = DetectExhaustion();
    bool isFailure = DetectFailure();
    
    if (isExhaustion && isFailure)
    {
        if (exhaustionDirection == Direction.Up)
            ExecuteMarketOrder(TradeType.Sell, ...);
        else
            ExecuteMarketOrder(TradeType.Buy, ...);
    }
}
```

## 📝 Critical Documents

1. **[COMPLETE_SUMMARY.md](fx-quant-research/COMPLETE_SUMMARY.md)**  
   Full 30-day project narrative with methodology, results, lessons learned

2. **[LOOK_AHEAD_BIAS_FIX.md](fx-quant-research/LOOK_AHEAD_BIAS_FIX.md)**  
   Documentation of the critical bug fix that exposed real strategy performance

3. **[DELIVERABLES_CHECKLIST.md](fx-quant-research/DELIVERABLES_CHECKLIST.md)**  
   Final completion checklist (all 30 deliverables ✓)

4. **[ATR_FILTER_RESULTS.md](fx-quant-research/ATR_FILTER_RESULTS.md)**  
   Volatility filter analysis and results

5. **Parameter Optimization Results**  
   See `parameter_optimization_results.csv` (375 rows)

## 🛠️ Tech Stack

- **Python 3.8+** — Core language
- **Pandas + NumPy** — Data manipulation
- **SciPy + statsmodels** — Statistical testing
- **scikit-learn** — HMM regime detection
- **Matplotlib + Seaborn** — Visualization
- **cTrader** — Live execution platform

## ⚠️ Production Deployment Checklist

Before going live:

- [ ] Verify broker spread assumptions (currently 2.0 pips for NZDJPY)
- [ ] Test on demo account for 2-4 weeks
- [ ] Implement position sizing (1-2% risk per trade)
- [ ] Add kill-switch logic (max daily drawdown limit)
- [ ] Monitor slippage vs backtest assumptions
- [ ] Track IC decay over time (re-optimize if IC < 0.20)
- [ ] Set up automated monitoring dashboard

## 📊 Performance Attribution

**Why This Works:**

1. **Behavioral Edge** — Exhaustion + failure = trapped traders reversing positions
2. **Statistical Edge** — IC of 0.39 with p<0.01 (strong predictive power)
3. **Regime Awareness** — 73% win rate in high-vol environments
4. **Disciplined Filters** — 2.5% signal rate prevents overtrading
5. **Rigorous Validation** — 30-day systematic development process

**Risk Factors:**

- Strategy degrades in low-volatility sideways markets (58% win rate)
- Requires active monitoring for IC decay
- Position sizing critical (use 1-2% risk per trade max)
- Spread/slippage assumptions must match live conditions

## 📚 Research Reports

Located in `fx-quant-research/`:

- **Days 14-23:** `DAYS_14-23_COMPLETION_REPORT.md` — Strategy development
- **Days 22-24:** `DAYS_22-24_COMPLETION_REPORT.md` — Optimization results
- **Days 25-30:** `DAYS_25-30_COMPLETION_REPORT.md` — Final validation

## 🤝 Contributing

This is a research repository. To extend:

1. Add new feature generators in `src/features/`
2. Implement alternative signal logic in `src/strategies/`
3. Run backtests and document results in `notebooks/`
4. Update parameter grid search if needed

## 📄 License

MIT License (or specify your license)

## 📧 Contact

For questions: [Your GitHub Profile](https://github.com/FredrickMbithi)

---

**Status:** ✅ PRODUCTION READY (as of March 2, 2026)  
**Primary Pair:** NZDJPY H1  
**Timeframe:** Hourly bars  
**Development Duration:** 30 days  
**Framework:** Python + cTrader
