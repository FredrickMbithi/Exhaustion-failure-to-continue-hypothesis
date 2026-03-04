# Switch to Python Version

If you want to use Python instead of C#, follow these steps:

## Step 1: Restore Python file

```bash
cd ctrader
mv ExhaustionFailureContinuation_main.py.backup ExhaustionFailureContinuation_main.py
```

## Step 2: Replace .cs file with parameters-only version

Delete all implementation code from ExhaustionFailureContinuation.cs, keep only:

```csharp
using cAlgo.API;

namespace cAlgo.Robots;

[Robot(AccessRights = AccessRights.None, AddIndicators = true)]
public partial class ExhaustionFailureContinuation : Robot
{
    // === Position Sizing & Risk Management ===
    [Parameter("Volume (Lots)", DefaultValue = 0.01, MinValue = 0.01, Step = 0.01, Group = "Risk Management")]
    public double VolumeInLots { get; set; }

    [Parameter("Stop Loss (Pips)", DefaultValue = 20, MinValue = 5, MaxValue = 200, Step = 1, Group = "Risk Management")]
    public double StopLossInPips { get; set; }

    [Parameter("Take Profit (Pips)", DefaultValue = 40, MinValue = 10, MaxValue = 500, Step = 1, Group = "Risk Management")]
    public double TakeProfitInPips { get; set; }

    [Parameter("Max Positions", DefaultValue = 1, MinValue = 1, MaxValue = 10, Step = 1, Group = "Risk Management")]
    public int MaxPositions { get; set; }

    [Parameter("Label", DefaultValue = "EFC_Bot", Group = "Risk Management")]
    public string Label { get; set; }

    // === Strategy Parameters (Optimized Values) ===
    [Parameter("Range Expansion Threshold", DefaultValue = 1.5, MinValue = 0.8, MaxValue = 3.0, Step = 0.1, Group = "Strategy")]
    public double RangeExpansionThreshold { get; set; }

    [Parameter("Extreme Zone Upper", DefaultValue = 0.85, MinValue = 0.6, MaxValue = 0.95, Step = 0.05, Group = "Strategy")]
    public double ExtremeZoneUpper { get; set; }

    [Parameter("Extreme Zone Lower", DefaultValue = 0.20, MinValue = 0.05, MaxValue = 0.4, Step = 0.05, Group = "Strategy")]
    public double ExtremeZoneLower { get; set; }

    [Parameter("Consecutive Bars", DefaultValue = 2, MinValue = 1, MaxValue = 5, Step = 1, Group = "Strategy")]
    public int ConsecutiveBars { get; set; }

    [Parameter("Range Lookback Period", DefaultValue = 20, MinValue = 10, MaxValue = 50, Step = 5, Group = "Strategy")]
    public int RangeLookbackPeriod { get; set; }

    // === Regime Detection (Optional) ===
    [Parameter("Enable Regime Filter", DefaultValue = false, Group = "Regime Detection")]
    public bool EnableRegimeFilter { get; set; }

    [Parameter("H4 Trend Period", DefaultValue = 50, MinValue = 20, MaxValue = 200, Step = 10, Group = "Regime Detection")]
    public int H4TrendPeriod { get; set; }

    [Parameter("D1 Trend Period", DefaultValue = 100, MinValue = 50, MaxValue = 300, Step = 20, Group = "Regime Detection")]
    public int D1TrendPeriod { get; set; }

    [Parameter("Only Trade Ranging Markets", DefaultValue = true, Group = "Regime Detection")]
    public bool OnlyTradeRanging { get; set; }

    // === Logging ===
    [Parameter("Enable Detailed Logging", DefaultValue = true, Group = "Logging")]
    public bool EnableLogging { get; set; }

    [Parameter("Log Signal Details", DefaultValue = false, Group = "Logging")]
    public bool LogSignalDetails { get; set; }
}
```

## Step 3: Rebuild in cTrader

That's it - the Python file will now execute!

## C# vs Python

**C# Advantages:**

- Faster execution
- Better IDE support in cTrader
- Native to cTrader platform
- Can be compiled and protected

**Python Advantages:**

- More readable syntax
- Easier to modify quickly
- Familiar if coming from Python background
- Good for rapid prototyping

**Recommendation:** Use C# for production (what you have now is perfect!)
