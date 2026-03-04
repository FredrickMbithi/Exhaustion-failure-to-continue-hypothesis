# cTrader Deployment Guide

## Exhaustion-Failure-to-Continue Strategy

**Strategy:** Counter-trend mean reversion  
**Validated Performance:** 65.38% win rate on NZDJPY  
**Monte Carlo Confidence:** 85-95% probability profitable

---

## Quick Deployment (5 Minutes)

### Step 1: Create cBot in cTrader

1. Open **cTrader Windows** or **cTrader Mac**
2. Navigate to **Automate** → **New cBot**
3. Name: `ExhaustionFailureContinuation`
4. Method: **"Using template"**
5. Language: **Python**
6. Click **Create**

### Step 2: Locate cBot Folder

1. Right-click the newly created cBot
2. Select **"Show in folder"**
3. Navigate to: `ExhaustionFailureContinuation/ExhaustionFailureContinuation/`

You should see files like:

```
ExhaustionFailureContinuation.cs
ExhaustionFailureContinuation.json
ExhaustionFailureContinuation_main.py
```

### Step 3: Replace Files

1. **DELETE** the auto-generated `.cs` file
2. **COPY** `ExhaustionFailureContinuation.cs` from this folder → cTrader folder
3. **DELETE** the auto-generated `_main.py` file
4. **COPY** `ExhaustionFailureContinuation_main.py` from this folder → cTrader folder

### Step 4: Build

1. Return to cTrader
2. Click **"Save and Build"**
3. Wait for "Build successful" message

✅ **If build successful, proceed to Step 5**  
❌ **If errors, verify file names match exactly**

### Step 5: Configure for Paper Trading

1. Click **"Add Instance"**
2. Configure:
   - **Account:** Pepperstone Demo (50,000)
   - **Symbol:** NZDJPY (recommended)
   - **Timeframe:** H1 (1 hour)
   - **Volume:** 0.01 lots
   - **Stop Loss:** 20 pips
   - **Take Profit:** 40 pips
   - **Max Positions:** 1

### Step 6: Start Paper Trading

1. Click **"Start"**
2. Monitor the **Log** tab for output
3. You should see:
   ```
   === Exhaustion-Failure-to-Continue Strategy Started ===
   Symbol: NZDJPY
   Timeframe: H1
   Volume per trade: 0.01 lots
   Parameters: Range Expansion=1.5, Extreme Zones=[0.2, 0.85], Consecutive Bars=2
   ```

---

## Parameter Configuration

### ✅ OPTIMIZED (Do Not Change)

These are validated optimal values from 375-combination grid search:

| Parameter                 | Value    | Range    | Description                        |
| ------------------------- | -------- | -------- | ---------------------------------- |
| Range Expansion Threshold | **1.5**  | 0.8-3.0  | Range must be 1.5x average         |
| Extreme Zone Upper        | **0.85** | 0.6-0.95 | Long signals: close in top 15%     |
| Extreme Zone Lower        | **0.20** | 0.05-0.4 | Short signals: close in bottom 20% |
| Consecutive Bars          | **2**    | 1-5      | Exhaustion must persist 2 bars     |
| Range Lookback Period     | **20**   | 10-50    | Average range calculation period   |

### ⚙️ ADJUSTABLE (Risk Management)

| Parameter          | Default | Adjust For     | Notes                   |
| ------------------ | ------- | -------------- | ----------------------- |
| Volume (Lots)      | 0.01    | Account size   | Start small (0.01-0.02) |
| Stop Loss (Pips)   | 20      | Volatility     | 15-30 pips typical      |
| Take Profit (Pips) | 40      | Reward/Risk    | Maintain 2:1 minimum    |
| Max Positions      | 1       | Risk tolerance | 1-3 for pyramiding      |

### 🔧 OPTIONAL (Advanced)

| Parameter               | Default | Purpose                 |
| ----------------------- | ------- | ----------------------- |
| Enable Regime Filter    | false   | Filter by market regime |
| Only Trade Ranging      | true    | Skip trending markets   |
| Enable Detailed Logging | true    | Show all events         |
| Log Signal Details      | false   | Debug mode (verbose)    |

---

## Expected Performance (NZDJPY, H1)

Based on 3-month backtest + Monte Carlo validation:

| Metric                       | Value  | Notes                          |
| ---------------------------- | ------ | ------------------------------ |
| **Win Rate**                 | 65.38% | Validated on 52 trades         |
| **Signal Frequency**         | 2.54%  | ~10-11 signals/month           |
| **IC**                       | 0.3934 | Highly significant (p=0.0039)  |
| **Sharpe Ratio**             | 28.26  | Exceptional                    |
| **Probability Profitable**   | 85-95% | Monte Carlo (1000 simulations) |
| **Expected Monthly Return**  | 3-6%   | At 2% risk per trade           |
| **Max Drawdown (95th %ile)** | 15-20% | From bootstrap                 |

---

## Monitoring Checklist

### ✅ First 24 Hours

- [ ] Verify strategy is running (check Log tab)
- [ ] Confirm parameters loaded correctly
- [ ] Monitor for first signal (may take 1-3 days)
- [ ] Check order execution (no errors)

### ✅ First Week

- [ ] Track signals generated (expect 2-3 on NZDJPY)
- [ ] Monitor win rate (should trend toward 60-65%)
- [ ] Compare slippage to backtest (2-3 pips typical)
- [ ] Verify SL/TP execution

### ✅ First Month

- [ ] Total signals: 10-11 expected
- [ ] Win rate: 60-65% target
- [ ] Signal rate: ~2.5% (not too high/low)
- [ ] Review if adjustments needed

---

## Recommended Pairs

### Primary (Validated)

- **NZDJPY** - 65.38% WR, IC=0.39 ✅ **BEST**
- **USDJPY** - 57.45% WR, IC=0.06 ⚠️ Monitor

### To Test (Paper Trade First)

- **AUDNZD** - Counter-trend candidate
- **EURAUD** - Low correlation with JPY pairs
- **GBPNZD** - Volatile, high signal potential

### Avoid

- **GBPUSD** - Tested, random results (50% WR)
- **EURCHF** - Tested, no edge detected
- **EURUSD** - Not yet tested, likely too liquid

---

## Troubleshooting

### Problem: No Signals Generated

**Solution:**

- Verify timeframe is H1 (not H4 or M15)
- Check "Enable Detailed Logging" = true
- Wait 24-48 hours (signals are rare by design: ~2.5% rate)

### Problem: Too Many Signals

**Possible causes:**

- Range Expansion too low (should be 1.5)
- Extreme Zones too wide (should be 0.85/0.20)
- Wrong timeframe (should be H1)

### Problem: All Losses

**Possible causes:**

- Incorrect parameters (verify defaults loaded)
- High slippage environment (use ECN account)
- Different broker pricing vs backtest data
- Consider adjusting SL/TP for live conditions

### Problem: Build Errors

**Solutions:**

- Verify file names: `ExhaustionFailureContinuation.cs` (no spaces)
- Verify Python file: `ExhaustionFailureContinuation_main.py`
- Check both files in same folder
- Delete `.json` file if present (parameters in `.cs` only)

---

## Risk Warnings

⚠️ **Small Sample Size:** Only 52 trades validated (need 100+ for stable estimates)

⚠️ **Time Period:** 3-month backtest may not capture all market regimes

⚠️ **Pair-Specific:** Performance varies by pair - always paper trade new pairs first

⚠️ **Slippage:** Live trading will have 1-3 pip slippage vs backtest

⚠️ **Regime Changes:** Strategy designed for ranging markets, may underperform in strong trends

⚠️ **Correlation Risk:** USDJPY + NZDJPY both JPY pairs (correlation ~0.3-0.5)

---

## Support & Enhancement

**Validated Strategy Code:** `src/strategies/exhaustion_failure.py`  
**Full Documentation:** `COMPLETE_SUMMARY.md`  
**Performance Reports:**

- `DAYS_22-24_COMPLETION_REPORT.md` (Parameter optimization)
- `DAYS_25-30_COMPLETION_REPORT.md` (Advanced features)

**Questions?** Check `PROJECT_STATUS.md` for quick reference

---

**Status:** ✅ Production Ready - Paper Trading Phase  
**Next Phase:** Live deployment after 2-4 weeks successful paper trading  
**Version:** 1.0.0 (March 2, 2026)
