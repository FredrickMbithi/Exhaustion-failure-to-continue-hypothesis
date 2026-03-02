"""
Diagnose Signal Filter Performance
Test each filter individually to see which helps vs hurts
"""
import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
from src.filters.signal_filters import SignalFilter

def test_filter_individually(pair: str, signals: pd.Series, returns: pd.Series, 
                              filter_name: str, filter_mask: pd.Series):
    """Test performance with individual filter applied"""
    
    filtered_signals = signals.copy()
    filtered_signals[~filter_mask] = 0
    
    # Count signals
    n_original = (signals != 0).sum()
    n_filtered = (filtered_signals != 0).sum()
    
    if n_filtered < 5:
        return {
            'pair': pair,
            'filter': filter_name,
            'signals': n_filtered,
            'win_rate': np.nan,
            'ic': np.nan,
            'ic_pval': np.nan,
            'note': 'Too few signals'
        }
    
    # Calculate performance
    strategy_returns = returns * filtered_signals.shift(1)
    valid = pd.DataFrame({
        'signal': filtered_signals,
        'forward_returns': returns,
        'strategy_returns': strategy_returns
    }).dropna()
    
    # Win rate
    trades = valid[valid['signal'] != 0]
    if len(trades) > 0:
        win_rate = (trades['strategy_returns'] > 0).sum() / len(trades) * 100
    else:
        win_rate = np.nan
    
    # IC
    from scipy.stats import pearsonr
    if len(valid) > 5:
        ic, ic_pval = pearsonr(valid['signal'], valid['forward_returns'])
    else:
        ic, ic_pval = np.nan, np.nan
    
    return {
        'pair': pair,
        'filter': filter_name,
        'signals': n_filtered,
        'reduction': f"{(1 - n_filtered/n_original)*100:.1f}%",
        'win_rate': win_rate,
        'ic': ic,
        'ic_pval': ic_pval
    }

def main():
    print("=" * 70)
    print("FILTER DIAGNOSTIC TEST")
    print("Testing each filter individually")
    print("=" * 70)
    
    # Best parameters from optimization
    params = {
        'range_expansion_threshold': 1.5,
        'extreme_zone_upper': 0.85,
        'extreme_zone_lower': 0.20,
        'consecutive_bars_required': 2
    }
    
    loader = FXDataLoader()
    strategy = ExhaustionFailureStrategy(**params)
    feature_eng = FeatureEngineering()
    
    pairs = ['USDJPY', 'NZDJPY']
    results = []
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    
    for pair in pairs:
        print(f"\n{'=' * 70}")
        print(f"Testing {pair}")
        print("=" * 70)
        
        # Load data
        csv_path = data_dir / f"{pair}60.csv"
        df, _ = loader.load_csv(str(csv_path), pair=pair)
        
        # Add features
        df = feature_eng.add_all_features(df)
        
        print(f"✅ Loaded {len(df)} bars")
        
        # Generate signals with optimized parameters
        df_with_signals = strategy.generate_signals(df)
        signals = df_with_signals['signal']
        
        n_signals = (signals != 0).sum()
        print(f"Raw signals: {n_signals}")
        
        # Baseline performance (no filters)
        returns = df['close'].pct_change()
        strategy_returns = returns * signals.shift(1)
        valid = pd.DataFrame({
            'signal': signals,
            'forward_returns': returns,
            'strategy_returns': strategy_returns
        }).dropna()
        
        trades = valid[valid['signal'] != 0]
        baseline_win_rate = (trades['strategy_returns'] > 0).sum() / len(trades) * 100
        
        from scipy.stats import pearsonr
        baseline_ic, baseline_pval = pearsonr(valid['signal'], valid['forward_returns'])
        
        print(f"Baseline (no filters): {baseline_win_rate:.2f}% win rate, IC={baseline_ic:.4f} (p={baseline_pval:.4f})")
        
        results.append({
            'pair': pair,
            'filter': 'BASELINE (no filters)',
            'signals': n_signals,
            'reduction': '0%',
            'win_rate': baseline_win_rate,
            'ic': baseline_ic,
            'ic_pval': baseline_pval
        })
        
        # Initialize filters
        signal_filter = SignalFilter(
            volatility_percentile=60,
            liquid_hours_start=8,
            liquid_hours_end=17,
            adx_threshold=25
        )
        
        # Test each filter individually
        print("\nTesting individual filters:")
        
        # 1. Volatility filter
        vol_mask = signal_filter.detect_volatility_regime(df)
        result = test_filter_individually(pair, signals, returns, 
                                         'Volatility (top 60%)', vol_mask)
        print(f"  Volatility: {result['signals']} signals, {result['win_rate']:.2f}% win rate")
        results.append(result)
        
        # 2. Time filter
        time_mask = signal_filter.detect_liquid_hours(df)
        result = test_filter_individually(pair, signals, returns, 
                                         'Time (08:00-17:00)', time_mask)
        print(f"  Time: {result['signals']} signals, {result['win_rate']:.2f}% win rate")
        results.append(result)
        
        # 3. ADX filter
        adx_mask = signal_filter.detect_ranging_market(df)
        result = test_filter_individually(pair, signals, returns, 
                                         'ADX (ranging)', adx_mask)
        print(f"  ADX: {result['signals']} signals, {result['win_rate']:.2f}% win rate")
        results.append(result)
        
        # 4. ALL filters combined
        all_mask = signal_filter.apply_filters(df)
        result = test_filter_individually(pair, signals, returns, 
                                         'ALL COMBINED', all_mask)
        print(f"  ALL: {result['signals']} signals, {result.get('win_rate', 'N/A')} win rate")
        results.append(result)
    
    # Summary table
    print("\n" + "=" * 70)
    print("FILTER PERFORMANCE SUMMARY")
    print("=" * 70)
    
    df_results = pd.DataFrame(results)
    
    print("\n📊 Complete Results:")
    print(df_results.to_string(index=False))
    
    # Save results
    output_path = Path(__file__).parent.parent / 'filter_diagnostic_results.csv'
    df_results.to_csv(output_path, index=False)
    print(f"\n✅ Results saved to {output_path}")
    
    print("\n" + "=" * 70)
    print("KEY INSIGHTS:")
    print("=" * 70)
    
    for pair in pairs:
        pair_data = df_results[df_results['pair'] == pair]
        baseline = pair_data[pair_data['filter'] == 'BASELINE (no filters)'].iloc[0]
        
        print(f"\n{pair}:")
        print(f"  Baseline: {baseline['win_rate']:.2f}% win rate ({baseline['signals']} signals)")
        
        # Find best individual filter
        individual_filters = pair_data[
            ~pair_data['filter'].isin(['BASELINE (no filters)', 'ALL COMBINED'])
        ]
        
        if len(individual_filters) > 0:
            valid_filters = individual_filters[individual_filters['win_rate'].notna()]
            if len(valid_filters) > 0:
                best = valid_filters.loc[valid_filters['win_rate'].idxmax()]
                print(f"  Best filter: {best['filter']} -> {best['win_rate']:.2f}% win rate ({best['signals']} signals)")
                
                worst = valid_filters.loc[valid_filters['win_rate'].idxmin()]
                print(f"  Worst filter: {worst['filter']} -> {worst['win_rate']:.2f}% win rate ({worst['signals']} signals)")

if __name__ == "__main__":
    main()
