"""
Test optimized parameters with signal filters.

Days 22-24: Combine best parameters from optimization with signal filters.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
from src.filters.signal_filters import SignalFilter
from scipy.stats import spearmanr


def test_optimized_strategy(pair: str, data_dir: Path) -> dict:
    """Test strategy with optimized parameters and filters."""
    
    print(f"\n{'='*60}")
    print(f"Testing {pair} with Optimized Parameters + Filters")
    print(f"{'='*60}")
    
    # Load data
    csv_path = data_dir / f"{pair}60.csv"
    if not csv_path.exists():
        print(f"❌ File not found")
        return None
    
    loader = FXDataLoader()
    df, metadata = loader.load_csv(str(csv_path), pair)
    print(f"✅ Loaded {len(df)} bars")
    
    # Add features
    fe = FeatureEngineering()
    df = fe.add_momentum(df, windows=[5, 10, 20])
    df = fe.add_volatility_features(df)
    df = fe.add_range_features(df, windows=[10, 20, 50])
    df = fe.add_close_position(df)
    df = fe.add_consecutive_direction(df, windows=[2, 3])
    df = fe.add_range_breakout_features(df, windows=[10, 20, 50])
    
    # Best parameters from optimization
    print("\n📊 Using Optimized Parameters:")
    print("  Range expansion: 1.5 (was 0.8)")
    print("  Extreme upper: 0.85 (was 0.65)")
    print("  Extreme lower: 0.20 (was 0.35)")
    print("  Consecutive bars: 2 (unchanged)")
    
    strategy = ExhaustionFailureStrategy(
        range_expansion_threshold=1.5,
        median_range_window=20,
        extreme_zone_upper=0.85,
        extreme_zone_lower=0.20,
        consecutive_bars_required=2,
        enable_failure_filter=True
    )
    
    # Generate raw signals
    signals_raw = strategy.generate_signals(df)
    diagnostics_raw = strategy.get_signal_diagnostics(df)
    
    print(f"\n🔧 Raw Signal Generation:")
    print(f"  Exhaustions: {diagnostics_raw['total_exhaustion']}")
    print(f"  Raw signals: {diagnostics_raw['total_signals']}")
    print(f"  Reduction ratio: {diagnostics_raw['reduction_ratio']:.1%}")
    
    # Apply filters
    print(f"\n🔍 Applying Signal Filters:")
    print("  1. Volatility regime: Top 60% volatility periods")
    print("  2. Time-of-day: 08:00-17:00 UTC")
    print("  3. Trend strength: ADX < 25% (ranging markets)")
    
    signal_filter = SignalFilter(
        vol_window=20,
        vol_threshold_percentile=60.0,
        liquid_hours_start="08:00",
        liquid_hours_end="17:00",
        trend_window=20,
        trend_threshold=0.25
    )
    
    signals_filtered, filter_diagnostics = signal_filter.apply_filters(
        df, signals_raw,
        enable_vol_filter=True,
        enable_time_filter=True,
        enable_trend_filter=True
    )
    
    filter_stats = signal_filter.get_filter_statistics(filter_diagnostics)
    
    print(f"\n📉 Filter Impact:")
    print(f"  Original signals: {filter_stats['original_signals']}")
    print(f"  After filters: {filter_stats['filtered_signals']}")
    print(f"  Reduction: {filter_stats['reduction_ratio']*100:.1f}%")
    print(f"  Signal rate: {filter_stats['filtered_signals']/len(df)*100:.2f}% of bars")
    
    # Calculate performance for both
    df['returns'] = df['close'].pct_change()
    df['forward_returns'] = df['returns'].shift(-1)
    
    results = {}
    
    for signal_type, signals in [('Raw', signals_raw), ('Filtered', signals_filtered)]:
        df['signal'] = signals
        df['strategy_returns'] = signals * df['forward_returns']
        valid = df[['signal', 'forward_returns', 'strategy_returns']].dropna()
        
        signal_days = valid[valid['signal'] != 0]
        
        if len(signal_days) > 10:
            win_rate = (signal_days['strategy_returns'] > 0).mean()
            mean_return = signal_days['strategy_returns'].mean()
            std_return = signal_days['strategy_returns'].std()
            sharpe = mean_return / std_return * (252 * 24)**0.5 if std_return > 0 else 0
            ic, ic_pval = spearmanr(signal_days['signal'], signal_days['forward_returns'])
            
            results[signal_type] = {
                'signals': len(signal_days),
                'win_rate': win_rate * 100,
                'mean_return': mean_return,
                'sharpe': sharpe,
                'ic': ic,
                'ic_pval': ic_pval
            }
        else:
            results[signal_type] = {
                'signals': len(signal_days),
                'win_rate': 0,
                'mean_return': 0,
                'sharpe': 0,
                'ic': 0,
                'ic_pval': 1.0
            }
    
    # Print comparison
    print(f"\n{'='*60}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*60}")
    
    print(f"\n{'Metric':<20} {'Raw':>15} {'Filtered':>15} {'Change':>15}")
    print("-" * 70)
    
    for metric in ['signals', 'win_rate', 'sharpe', 'ic', 'ic_pval']:
        raw_val = results['Raw'][metric]
        filt_val = results['Filtered'][metric]
        
        if metric == 'signals':
            change = f"{filt_val - raw_val:+.0f}"
            print(f"{metric:<20} {raw_val:>15.0f} {filt_val:>15.0f} {change:>15}")
        elif metric == 'ic_pval':
            change = f"{filt_val - raw_val:+.4f}"
            print(f"{metric:<20} {raw_val:>15.4f} {filt_val:>15.4f} {change:>15}")
        elif metric in ['win_rate']:
            change = f"{filt_val - raw_val:+.2f}%"
            print(f"{metric:<20} {raw_val:>14.2f}% {filt_val:>14.2f}% {change:>15}")
        else:
            change = f"{filt_val - raw_val:+.4f}"
            print(f"{metric:<20} {raw_val:>15.4f} {filt_val:>15.4f} {change:>15}")
    
    # Goal assessment
    print(f"\n{'='*60}")
    print("GOAL ASSESSMENT")
    print(f"{'='*60}")
    
    goals = {
        'Win Rate ≥ 60%': results['Filtered']['win_rate'] >= 60.0,
        'Signal Rate < 5%': (filter_stats['filtered_signals'] / len(df) * 100) < 5.0,
        'IC > 0.2': results['Filtered']['ic'] > 0.2,
        'IC p-value < 0.05': results['Filtered']['ic_pval'] < 0.05,
        'Sharpe > 1.5': results['Filtered']['sharpe'] > 1.5
    }
    
    for goal, met in goals.items():
        status = "✅" if met else "❌"
        print(f"{status} {goal}")
    
    all_met = all(goals.values())
    print(f"\n{'✅ ALL GOALS MET!' if all_met else '⚠️  Some goals not met'}")
    
    return {
        'pair': pair,
        'raw': results['Raw'],
        'filtered': results['Filtered'],
        'filter_stats': filter_stats,
        'goals_met': all_met
}


def main():
    """Main testing routine."""
    
    print("="*60)
    print("OPTIMIZED STRATEGY + FILTERS TEST")
    print("Days 22-24 Completion")
    print("="*60)
    
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    pairs = ["USDJPY", "NZDJPY"]
    
    results = []
    for pair in pairs:
        result = test_optimized_strategy(pair, data_dir)
        if result:
            results.append(result)
    
    # Summary
    if results:
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        
        for result in results:
            pair = result['pair']
            filt = result['filtered']
            signal_rate = result['filter_stats']['filtered_signals'] / 2048 * 100
            
            print(f"\n{pair}:")
            print(f"  Win Rate: {filt['win_rate']:.2f}% {'✅' if filt['win_rate'] >= 60 else '❌'}")
            print(f"  Signal Rate: {signal_rate:.2f}% {'✅' if signal_rate < 5 else '❌'}")
            print(f"  IC: {filt['ic']:.4f} (p={filt['ic_pval']:.4f}) {'✅' if filt['ic'] > 0.2 and filt['ic_pval'] < 0.05 else '❌'}")
            print(f"  Sharpe: {filt['sharpe']:.2f} {'✅' if filt['sharpe'] > 1.5 else '❌'}")
            print(f"  Goals Met: {'ALL ✅' if result['goals_met'] else 'PARTIAL ⚠️'}")
    
    print(f"\n{'='*60}")
    print("DAYS 22-24: PARAMETER OPTIMIZATION + FILTERING COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
