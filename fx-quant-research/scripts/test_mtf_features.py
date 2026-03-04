"""
Test multi-timeframe features on USDJPY and NZDJPY.

Tests:
1. Resample H1 → H4, D1
2. Calculate trend, volatility regime, ADX
3. Test if MTF filtering improves strategy performance
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.multi_timeframe import MultiTimeframeFeatures


def test_mtf_filtering(pair: str, data_dir: Path) -> dict:
    """Test if multi-timeframe filtering improves performance."""
    
    print(f"\n{'='*70}")
    print(f"Testing {pair} with Multi-Timeframe Features")
    print("="*70)
    
    # Load data
    csv_path = data_dir / f"{pair}60.csv"
    loader = FXDataLoader()
    df, _ = loader.load_csv(str(csv_path), pair=pair)
    print(f"✅ Loaded {len(df)} bars")
    
    # Add MTF features
    mtf = MultiTimeframeFeatures()
    df = mtf.add_higher_tf_features(df, include_h4=True, include_d1=True)
    print(f"✅ Added H4 and D1 features")
    
    # MTF report
    report = mtf.generate_report(df)
    print(f"\n📊 Multi-Timeframe Analysis:")
    if 'h4_trend_distribution' in report:
        print(f"  H4 Trends: {report['h4_trend_distribution']['uptrend_pct']:.1f}% up, "
              f"{report['h4_trend_distribution']['downtrend_pct']:.1f}% down, "
              f"{report['h4_trend_distribution']['ranging_pct']:.1f}% ranging")
    if 'd1_trend_distribution' in report:
        print(f"  D1 Trends: {report['d1_trend_distribution']['uptrend_pct']:.1f}% up, "
              f"{report['d1_trend_distribution']['downtrend_pct']:.1f}% down, "
              f"{report['d1_trend_distribution']['ranging_pct']:.1f}% ranging")
    if 'tf_alignment_pct' in report:
        print(f"  TF Alignment: {report['tf_alignment_pct']:.1f}% of time")
    
    # Generate signals with optimized parameters
    strategy = ExhaustionFailureStrategy(
        range_expansion_threshold=1.5,
        extreme_zone_upper=0.85,
        extreme_zone_lower=0.20,
        consecutive_bars_required=2
    )
    
    df_with_signals = strategy.generate_signals(df)
    signals = df_with_signals['signal']
    
    # Calculate returns
    returns = df['close'].pct_change()
    strategy_returns = returns * signals.shift(1)
    
    # Baseline performance (no MTF filtering)
    valid = pd.DataFrame({
        'signal': signals,
        'returns': returns,
        'strat_returns': strategy_returns
    }).dropna()
    
    trades = valid[valid['signal'] != 0]
    n_baseline = len(trades)
    baseline_wr = (trades['strat_returns'] > 0).mean() * 100 if n_baseline > 0 else 0
    baseline_ic, baseline_pval = pearsonr(valid['signal'], valid['returns']) if len(valid) > 5 else (0, 1)
    
    print(f"\n🎯 Baseline (no MTF filter):")
    print(f"  Signals: {n_baseline}")
    print(f"  Win Rate: {baseline_wr:.2f}%")
    print(f"  IC: {baseline_ic:.4f} (p={baseline_pval:.4f})")
    
    results = [{
        'pair': pair,
        'filter': 'BASELINE',
        'signals': n_baseline,
        'win_rate': baseline_wr,
        'ic': baseline_ic,
        'ic_pval': baseline_pval
    }]
    
    # Test MTF filters
    filters = [
        ('Ranging (H4 ADX<25)', lambda df: df['h4_adx'] < 25),
        ('Ranging (D1 ADX<25)', lambda df: df['d1_adx'] < 25),
        ('H4 Uptrend', lambda df: df['h4_trend'] == 1),
        ('H4 Downtrend', lambda df: df['h4_trend'] == -1),
        ('H4 Ranging', lambda df: df['h4_trend'] == 0),
        ('D1 Uptrend', lambda df: df['d1_trend'] == 1),
        ('D1 Downtrend', lambda df: df['d1_trend'] == -1),
        ('D1 Ranging', lambda df: df['d1_trend'] == 0),
        ('TF Aligned', mtf.get_multi_tf_alignment),
        ('H4 High Vol', lambda df: df['h4_high_vol']),
        ('D1 High Vol', lambda df: df['d1_high_vol']),
    ]
    
    print(f"\n🔍 Testing MTF Filters:")
    
    for filter_name, filter_func in filters:
        try:
            mask = filter_func(df_with_signals)
            
            # Apply filter
            filtered_signals = signals.copy()
            filtered_signals[~mask] = 0
            
            filtered_returns = returns * filtered_signals.shift(1)
            valid_filtered = pd.DataFrame({
                'signal': filtered_signals,
                'returns': returns,
                'strat_returns': filtered_returns
            }).dropna()
            
            trades_filtered = valid_filtered[valid_filtered['signal'] != 0]
            n_filtered = len(trades_filtered)
            
            if n_filtered < 5:
                print(f"  {filter_name:20s}: {n_filtered} signals (too few)")
                results.append({
                    'pair': pair,
                    'filter': filter_name,
                    'signals': n_filtered,
                    'win_rate': np.nan,
                    'ic': np.nan,
                    'ic_pval': np.nan
                })
                continue
            
            filtered_wr = (trades_filtered['strat_returns'] > 0).mean() * 100
            filtered_ic, filtered_pval = pearsonr(valid_filtered['signal'], valid_filtered['returns'])
            
            # Win rate change
            wr_change = filtered_wr - baseline_wr
            wr_symbol = "✅" if wr_change > 0 else "❌"
            
            print(f"  {filter_name:20s}: {n_filtered:3d} signals, {filtered_wr:5.1f}% WR ({wr_change:+.1f}pp) {wr_symbol}")
            
            results.append({
                'pair': pair,
                'filter': filter_name,
                'signals': n_filtered,
                'win_rate': filtered_wr,
                'ic': filtered_ic,
                'ic_pval': filtered_pval
            })
            
        except Exception as e:
            print(f"  {filter_name:20s}: ERROR - {e}")
    
    return results


def main():
    print("="*70)
    print("MULTI-TIMEFRAME FEATURE TESTING")
    print("Days 25-27: Enhanced Features")
    print("="*70)
    
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    pairs = ['USDJPY', 'NZDJPY']
    
    all_results = []
    
    for pair in pairs:
        results = test_mtf_filtering(pair, data_dir)
        all_results.extend(results)
    
    # Summary table
    print("\n" + "="*70)
    print("SUMMARY: Multi-Timeframe Filter Performance")
    print("="*70)
    
    df_results = pd.DataFrame(all_results)
    print(df_results.to_string(index=False))
    
    # Save results
    output_path = Path(__file__).parent.parent / 'mtf_filter_results.csv'
    df_results.to_csv(output_path, index=False)
    print(f"\n✅ Results saved to {output_path}")
    
    # Find best filters
    print("\n" + "="*70)
    print("BEST FILTERS BY PAIR:")
    print("="*70)
    
    for pair in pairs:
        pair_data = df_results[df_results['pair'] == pair]
        baseline = pair_data[pair_data['filter'] == 'BASELINE'].iloc[0]
        
        # Filter out baseline and invalid results
        filtered_data = pair_data[
            (pair_data['filter'] != 'BASELINE') & 
            (pair_data['win_rate'].notna()) &
            (pair_data['signals'] >= 10)  # At least 10 signals
        ]
        
        if len(filtered_data) == 0:
            print(f"\n{pair}: No valid filters with ≥10 signals")
            continue
        
        # Sort by win rate
        top_filters = filtered_data.nlargest(3, 'win_rate')
        
        print(f"\n{pair} (Baseline: {baseline['win_rate']:.1f}% WR, {baseline['signals']} signals):")
        for idx, row in top_filters.iterrows():
            improvement = row['win_rate'] - baseline['win_rate']
            print(f"  {row['filter']:20s}: {row['win_rate']:.1f}% WR ({improvement:+.1f}pp), {row['signals']} signals")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS:")
    print("="*70)
    print("- MTF filters tested individually to identify which improve performance")
    print("- Filters with <10 signals marked as 'too few'")
    print("- Positive improvement (✅) shows filter helps, negative (❌) shows it hurts")
    print("- Best performing filters should be combined (if independent)")
    print("="*70)


if __name__ == "__main__":
    main()
