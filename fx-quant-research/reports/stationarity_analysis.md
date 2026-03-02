# Stationarity Analysis Report

## Executive Summary

**Finding:** FX prices exhibit unit root behavior (non-stationary), while returns are stationary.

**Implication:** Trading strategies must operate on returns, not raw price levels.

## Test Results

| Pair   |   Price ADF p-val | Price Stationary   |   Return ADF p-val | Return Stationary   |
|:-------|------------------:|:-------------------|-------------------:|:--------------------|
| EURUSD |            0.5336 | ❌                 |                  0 | ✅                  |
| GBPUSD |            0.0633 | ❌                 |                  0 | ✅                  |
| USDJPY |            0.1266 | ❌                 |                  0 | ✅                  |

## Methodology

- **ADF Test**: Tests for unit root (H0 = non-stationary)
- **KPSS Test**: Tests for stationarity (H0 = stationary)
- **Conclusion**: Series is stationary if both tests agree (ADF rejects, KPSS accepts)
