"""
Simple Filter Diagnostic - Test filters individually
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.filters.signal_filters import SignalFilter


def analyze_filter(signals, returns, filter_mask, filter_name):
    """Analyze performance of signals with specific filter."""
    # Apply filter
    filtered_signals = signals.copy()
    filtered_signals[~filter_mask] = 0
    
    n_original = (signals != 0).sum()
    n_filtered = (filtered_signals != 0).sum()
    
    if n_filtered < 5:
        return {
            'filter': filter_name,
            'signals': n_filtered,
            'reduction': f"{100*(1-n_filtered/n_original):.1f}%",
            'win_rate': np.nan,
            'ic': np.nan,
            'ic_pval': np.nan,
            'note': 'Too few signals (<5)'
        }
    
    # Calculate metrics
    strategy_returns = returns * filtered_signals.shift(1)
    valid = pd.DataFrame({
        'signal': filtered_signals,
        'returns': returns,
        'strat_returns': strategy_returns
    }).dropna()
    
    # Win rate from actual trades
    trades = valid[valid['signal'] != 0]
    win_rate = (trades['strat_returns'] > 0).mean() * 100
    
    # IC
    ic, pval = pearsonr(valid['signal'], valid['returns'])
    
    return {
        'filter': filter_name,
        'signals': n_filtered,
        'reduction': f"{100*(1-n_filtered/n_original):.1f}%",
        'win_rate': win_rate,
        'ic': ic,
        'ic_pval': pval,
        'note': ''
    }


def main():
    print("="*70)
    print("SIMPLE FILTER DIAGNOSTIC")
    print("="*70)
    
    loader = FXDataLoader()
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    
    # Optimized parameters
    strategy = ExhaustionFailureStrategy(
        range_expansion_threshold=1.5,
        extreme_zone_upper=0.85,
        extreme_zone_lower=0.20,
        consecutive_bars_required=2
    )
    
    signal_filter = SignalFilter(
        volatility_percentile=60,
        liquid_hours_start=8,
        liquid_hours_end=17,
        adx_threshold=25
    )
    
    pairs = ['USDJPY', 'NZDJPY']
    all_results = []
    
    for pair in pairs:
        print(f"\n{'='*70}")
        print(f"{pair}")
        print("="*70)
        
        # Load
        csv_path = data_dir / f"{pair}60.csv"
        df, _ = loader.load_csv(str(csv_path), pair=pair)
        print(f"Loaded {len(df)} bars")
        
        # Generate signals (strategy already has features built in)
        df_signals = strategy.generate_signals(df)
        signals = df_signals['signal']
        returns = df['close'].pct_change()
        
        n_signals = (signals != 0).sum()
        print(f"Raw signals: {n_signals}")
        
        # Baseline
        strategy_returns = returns * signals.shift(1)
        valid = pd.DataFrame({
            'signal': signals,
            'returns': returns,
            'strat_returns': strategy_returns
        }).dropna()
        
        trades = valid[valid['signal'] != 0]
        baseline_wr = (trades['strat_returns'] > 0).mean() * 100
        baseline_ic, baseline_pval = pearsonr(valid['signal'], valid['returns'])
        
        print(f"Baseline: {baseline_wr:.1f}% WR, IC={baseline_ic:.4f} (p={baseline_pval:.4f})\n")
        
        all_results.append({
            'pair': pair,
            'filter': 'BASELINE',
            'signals': n_signals,
            'reduction': '0%',
            'win_rate': baseline_wr,
            'ic': baseline_ic,
            'ic_pval': baseline_pval,
            'note': ''
        })
        
        # Test individual filters
        print("Testing filters individually:")
        
        # Volatility
        vol_mask = signal_filter.detect_volatility_regime(df)
        result = analyze_filter(signals, returns, vol_mask, 'Volatility (top 60%)')
        print(f"  Vol: {result['signals']} signals, {result['win_rate']:.1f}% WR")
        result['pair'] = pair
        all_results.append(result)
        
        # Time
        time_mask = signal_filter.detect_liquid_hours(df)
        result = analyze_filter(signals, returns, time_mask, 'Time (08:00-17:00)')
        print(f"  Time: {result['signals']} signals, {result['win_rate']:.1f}% WR")
        result['pair'] = pair
        all_results.append(result)
        
        # ADX
        adx_mask = signal_filter.detect_ranging_market(df)
        result = analyze_filter(signals, returns, adx_mask, 'ADX (ranging)')
        print(f"  ADX: {result['signals']} signals, {result['win_rate']:.1f}% WR")
        result['pair'] = pair
        all_results.append(result)
        
        # All combined
        all_mask = signal_filter.apply_filters(df)
        result = analyze_filter(signals, returns, all_mask, 'ALL COMBINED')
        print(f"  ALL: {result['signals']} signals, {result.get('win_rate', 'N/A')} WR")
        result['pair'] = pair
        all_results.append(result)
    
    # Results table
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    
    df_results = pd.DataFrame(all_results)
    print(df_results.to_string(index=False))
    
    # Save
    output_path = Path(__file__).parent.parent / 'filter_diagnostic_results.csv'
    df_results.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")
    
    # Key insights
    print("\n" + "="*70)
    print("KEY FINDINGS:")
    print("="*70)
    
    for pair in pairs:
        pair_data = df_results[df_results['pair'] == pair]
        baseline = pair_data[pair_data['filter'] == 'BASELINE'].iloc[0]
        
        print(f"\n{pair}:")
        print(f"  Baseline: {baseline['win_rate']:.1f}% WR ({baseline['signals']} signals)")
        
        individual = pair_data[~pair_data['filter'].isin(['BASELINE', 'ALL COMBINED'])]
        individual = individual[individual['win_rate'].notna()]
        
        if len(individual) > 0:
            best = individual.loc[individual['win_rate'].idxmax()]
            worst = individual.loc[individual['win_rate'].idxmin()]
            
            print(f"  BEST: {best['filter']} → {best['win_rate']:.1f}% WR ({best['signals']} signals)")
            print(f"  WORST: {worst['filter']} → {worst['win_rate']:.1f}% WR ({worst['signals']} signals)")
            
        combined = pair_data[pair_data['filter'] == 'ALL COMBINED'].iloc[0]
        if not pd.isna(combined['win_rate']):
            print(f"  COMBINED: {combined['win_rate']:.1f}% WR ({combined['signals']} signals)")


if __name__ == "__main__":
    main()
