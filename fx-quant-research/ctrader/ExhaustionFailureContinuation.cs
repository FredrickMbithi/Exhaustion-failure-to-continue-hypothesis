using cAlgo.API;
using cAlgo.API.Internals;
using System;
using System.Linq;

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

    // === Internal state ===
    private long _volumeInUnits;
    private bool _exhaustionDetected;
    private string _exhaustionDirection; // "long" or "short"
    private int _exhaustionCount;
    private double _priorBarHigh;
    private double _priorBarLow;
    private int _barsProcessed;
    private int _totalSignals;
    private int _exhaustionBarIndex;

    protected override void OnStart()
    {
        _volumeInUnits = (long)Symbol.QuantityToVolumeInUnits(VolumeInLots);

        _exhaustionDetected = false;
        _exhaustionDirection = null;
        _exhaustionCount = 0;
        _barsProcessed = 0;
        _totalSignals = 0;
        _exhaustionBarIndex = -1;

        if (EnableLogging)
        {
            Print("=== Exhaustion-Failure-to-Continue Strategy Started ===");
            Print($"Symbol: {SymbolName}");
            Print($"Timeframe: {TimeFrame}");
            Print($"Volume per trade: {VolumeInLots} lots ({_volumeInUnits} units)");
            Print($"Parameters: Range Expansion={RangeExpansionThreshold}, Extreme Zones=[{ExtremeZoneLower}, {ExtremeZoneUpper}], Consecutive Bars={ConsecutiveBars}, Lookback={RangeLookbackPeriod}");
            Print(new string('=', 60));
        }
    }

    protected override void OnBar()
    {
        _barsProcessed++;

        // Need enough bars to compute averages
        if (Bars.Count < RangeLookbackPeriod + 3) // need current + prior + lookback history
            return;

        // Regime filter (currently passive hook)
        if (EnableRegimeFilter && !CheckRegimeConditions())
        {
            if (LogSignalDetails)
                Print("Regime filter: Market conditions not favorable");
            return;
        }

        // In cTrader, OnBar fires when a NEW bar opens; the just-closed bar is index 1
        var currentBar = Bars.Last(1); // most recently CLOSED bar
        var priorBar = Bars.Last(2);   // bar before that

        var currentRange = currentBar.High - currentBar.Low;
        var avgRange = CalculateAverageRange(RangeLookbackPeriod);
        var rangeExpansion = avgRange > 0 ? currentRange / avgRange : 0;
        var closePosition = CalculateClosePosition(currentBar);

        // === PHASE 1: Detect Exhaustion ===
        if (!_exhaustionDetected)
        {
            bool isExpanded = rangeExpansion >= RangeExpansionThreshold;
            bool isExtremeHigh = closePosition >= ExtremeZoneUpper;
            bool isExtremeLow = closePosition <= ExtremeZoneLower;

            if (isExpanded && isExtremeHigh)
            {
                _exhaustionCount++;
                if (_exhaustionCount >= ConsecutiveBars)
                {
                    _exhaustionDetected = true;
                    _exhaustionDirection = "short";
                    _priorBarHigh = priorBar.High;
                    _priorBarLow = priorBar.Low;
                    _exhaustionBarIndex = Bars.Count - 2; // index of closed bar that triggered exhaustion

                    if (LogSignalDetails)
                        Print($"[BAR {_barsProcessed}] Bearish exhaustion detected: Range Expansion={rangeExpansion:F2}, Close Position={closePosition:F2}");
                }
            }
            else if (isExpanded && isExtremeLow)
            {
                _exhaustionCount++;
                if (_exhaustionCount >= ConsecutiveBars)
                {
                    _exhaustionDetected = true;
                    _exhaustionDirection = "long";
                    _priorBarHigh = priorBar.High;
                    _priorBarLow = priorBar.Low;
                    _exhaustionBarIndex = Bars.Count - 2;

                    if (LogSignalDetails)
                        Print($"[BAR {_barsProcessed}] Bullish exhaustion detected: Range Expansion={rangeExpansion:F2}, Close Position={closePosition:F2}");
                }
            }
            else
            {
                _exhaustionCount = 0;
            }
        }
        // === PHASE 2: Wait for Failure & Enter ===
        else
        {
            bool failureDetected = false;

            if (_exhaustionDirection == "short")
            {
                failureDetected = currentBar.Close < _priorBarHigh;
                if (failureDetected && LogSignalDetails)
                    Print($"[BAR {_barsProcessed}] Failure detected: Close {currentBar.Close} < Prior High {_priorBarHigh}");
            }
            else if (_exhaustionDirection == "long")
            {
                failureDetected = currentBar.Close > _priorBarLow;
                if (failureDetected && LogSignalDetails)
                    Print($"[BAR {_barsProcessed}] Failure detected: Close {currentBar.Close} > Prior Low {_priorBarLow}");
            }

            if (failureDetected)
            {
                var tradeType = _exhaustionDirection == "long" ? TradeType.Buy : TradeType.Sell;
                ExecuteTrade(tradeType, currentBar);
                ResetExhaustionState();
            }
            else
            {
                // expire after 5 bars from detection
                var barsSinceDetection = (Bars.Count - 2) - _exhaustionBarIndex; // count closed bars since detection
                if (barsSinceDetection >= 5)
                {
                    if (LogSignalDetails)
                        Print($"[BAR {_barsProcessed}] Exhaustion expired without failure signal");
                    ResetExhaustionState();
                }
            }
        }
    }

    private void ExecuteTrade(TradeType tradeType, Bar currentBar)
    {
        // Position limit
        var currentPositions = Positions.Count(p => p.Label == Label);
        if (currentPositions >= MaxPositions)
        {
            if (EnableLogging)
                Print($"Max positions ({MaxPositions}) reached. Skipping trade.");
            return;
        }

        CloseOppositePositions(tradeType);

        var result = ExecuteMarketOrder(tradeType, SymbolName, _volumeInUnits, Label, StopLossInPips, TakeProfitInPips);

        _totalSignals++;

        if (result.IsSuccessful)
        {
            var directionStr = tradeType == TradeType.Buy ? "LONG" : "SHORT";
            if (EnableLogging)
                Print($"[SIGNAL #{_totalSignals}] {directionStr} @ {currentBar.Close:F5} | SL: {StopLossInPips} pips | TP: {TakeProfitInPips} pips");
        }
        else
        {
            Print($"Order failed: {result.Error}");
        }
    }

    private double CalculateAverageRange(int period)
    {
        double total = 0.0;
        for (int i = 1; i <= period; i++)
        {
            var bar = Bars.Last(i);
            total += (bar.High - bar.Low);
        }
        return total / period;
    }

    private double CalculateClosePosition(Bar bar)
    {
        var range = bar.High - bar.Low;
        if (Math.Abs(range) < double.Epsilon)
            return 0.5; // doji

        return (bar.Close - bar.Low) / range;
    }

    private bool CheckRegimeConditions()
    {
        // Placeholder for higher timeframe filter; currently always true
        return true;
    }

    private void ResetExhaustionState()
    {
        _exhaustionDetected = false;
        _exhaustionDirection = null;
        _exhaustionCount = 0;
        _priorBarHigh = 0;
        _priorBarLow = 0;
        _exhaustionBarIndex = -1;
    }

    private void CloseOppositePositions(TradeType tradeType)
    {
        foreach (var position in Positions.Where(p => p.Label == Label && p.TradeType != tradeType))
        {
            ClosePosition(position);
            if (EnableLogging)
                Print($"Closed opposite position: {position.Id}");
        }
    }

    protected override void OnStop()
    {
        if (EnableLogging)
        {
            var signalRate = _barsProcessed > 0 ? (_totalSignals / (double)_barsProcessed * 100) : 0;
            Print(new string('=', 60));
            Print("=== Bot Stopped ===");
            Print($"Total bars processed: {_barsProcessed}");
            Print($"Total signals generated: {_totalSignals}");
            Print($"Signal rate: {signalRate:F2}%");
            Print($"Open positions: {Positions.Count(p => p.Label == Label)}");
            Print(new string('=', 60));
        }
    }
}
