# ATR Filter Backtest Results - Exhaustion Failure Pattern

## Overview
Tested exhaustion failure-to-continue pattern on three forex pairs (H1 timeframe) with and without ATR(14) filter.

## Pattern Definition
- **Setup**: Two consecutive bullish candles with higher closes, followed by bearish candle closing below 2nd candle's open
- **Entry**: Short at next bar open
- **Stop**: Above failure bar high
- **Target**: 2R (twice the risk)
- **Lookback for swing low**: 20 bars prior to failure bar

## ATR Filter Rules
- **Calculate**: prior_move = (failure bar high - swing low) / ATR(14)
- **ATR > 6 filter**: Only take trades where prior_move_atr > 6 (exhaustion signal)
- **Rationale**: prior_move_atr < 3 suggests pullback; > 6 suggests exhaustion/capitulation

## Results

### Comparison Table

| Pair | Filter | Trades | Win Rate | Avg Win | Avg Loss | Expectancy |
|------|--------|--------|----------|---------|----------|------------|
| EURUSD | No filter | 128 | 32.8% | 2.00R | -1.00R | -0.02R |
| EURUSD | ATR > 6 | 8 | 25.0% | 2.00R | -1.00R | -0.25R |
| USDJPY | No filter | 122 | 31.1% | 2.00R | -1.00R | -0.07R |
| USDJPY | ATR > 6 | 9 | 11.1% | 2.00R | -1.00R | -0.67R |
| GBPUSD | No filter | 599 | 31.4% | 2.00R | -1.00R | -0.06R |
| GBPUSD | ATR > 6 | 56 | 21.4% | 2.00R | -1.00R | -0.36R |

---

## Key Findings

### 1. ❌ Does the 100% win rate from EURUSD hold on other pairs?
**NO.** The pattern shows ~31-33% win rate consistently across all three pairs:
- EURUSD: 32.8% (no filter), 25.0% (ATR > 6)
- USDJPY: 31.1% (no filter), 11.1% (ATR > 6)  
- GBPUSD: 31.4% (no filter), 21.4% (ATR > 6)

There is no 100% win rate. The pattern is **consistently unprofitable** across all pairs.

### 2. ❌ Does ATR > 6 filtering improve expectancy?
**NO.** The ATR > 6 filter actually **WORSENS** expectancy on all pairs:
- **EURUSD**: -0.02R → -0.25R (-0.23R deterioration)
- **USDJPY**: -0.07R → -0.67R (-0.60R deterioration) **[WORST]**
- **GBPUSD**: -0.06R → -0.36R (-0.30R deterioration)

The filter is counterproductive. It selects for higher-magnitude moves, but these actually perform *worse* than the unfiltered pattern.

### 3. Which pair performs best with the ATR filter?
**EURUSD** is the least bad with ATR > 6 filtering:
- Expectancy: -0.25R
- Trade count: 8 (very selective)
- Win rate: 25.0%

However, **all pairs are unprofitable** even with the filter. GBPUSD has more trades (56) but worse expectancy (-0.36R).

---

## Data Summary
- **EURUSD**: 2,047 bars (H1)
- **USDJPY**: 2,048 bars (H1)
- **GBPUSD**: 10,000 bars (H1, limited as requested)

---

## Conclusion

The exhaustion failure-to-continue pattern, as currently defined, **does not generate edge** across EURUSD, USDJPY, or GBPUSD. Key issues:

1. **Low win rate** (~31%) insufficient to overcome 1R:2R risk/reward ratio
2. **ATR filter fails** to improve the pattern; higher prior moves correlate with *worse* outcomes
3. **Inconsistent across pairs** - No single pair shows profitability

**Recommendation**: This pattern and filter combination requires rethinking. Either:
- Redefine pattern parameters (maybe longer/shorter lookbacks, different candle requirements)
- Explore different filters (volatility-adjusted stops, market regime detection)
- Test on other timeframes or instrument classes
- Abandon this hypothesis in favor of a different edge

