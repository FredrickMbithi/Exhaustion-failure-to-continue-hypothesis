"""
Cross-pair validation for exhaustion-failure strategy.

Tests strategy consistency across all FX pairs to ensure:
1. Signal generation is stable across instruments
2. IC maintains sign and magnitude
3. Performance metrics are economically meaningful
4. No pair-specific overfitting
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.loader import FXDataLoader
from src.features.library import FeatureEngineering
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.analysis.univariate_test import (
    compute_information_coefficient,
    compute_hac_tstat,
    test_stationarity
)


def load_all_pairs(data_dir: Path) -> Dict[str, pd.DataFrame]:
    """
    Load all FX pairs from data directory.
    
    Args:
        data_dir: Directory containing CSV files
        
    Returns:
        Dict mapping pair name to DataFrame
    """
    loader = FXDataLoader()
    pairs = {}
    
    # Get all CSV files
    csv_files = list(data_dir.glob("*.csv"))
    
    for csv_file in csv_files:
        pair = csv_file.stem.replace("60", "")  # Remove timeframe suffix
        try:
            df, metadata = loader.load_csv(str(csv_file), pair=pair)
            if df is not None and len(df) > 0:
                pairs[pair] = df
                print(f"✓ Loaded {pair}: {len(df)} bars")
        except Exception as e:
            print(f"✗ Failed to load {pair}: {e}")
    
    return pairs


def generate_strategy_signals(
    df: pd.DataFrame,
    strategy: ExhaustionFailureStrategy
) -> Tuple[pd.DataFrame, Dict]:
    """
    Generate exhaustion-failure signals for a pair.
    
    Args:
        df: OHLCV data
        strategy: Strategy instance
        
    Returns:
        Tuple of (df with signals, diagnostics)
    """
    # Add features
    fe = FeatureEngineering()
    df_features = df.copy()
    df_features = fe.add_momentum(df_features, windows=[5, 10, 20])
    df_features = fe.add_volatility_features(df_features)
    df_features = fe.add_range_features(df_features, windows=[10, 20, 50])
    df_features = fe.add_close_position(df_features)
    df_features = fe.add_consecutive_direction(df_features, windows=[2, 3])
    df_features = fe.add_range_breakout_features(df_features, windows=[10, 20, 50])
    
    # Generate signals
    signals = strategy.generate_signals(df_features)
    df_features['signal'] = signals
    
    # Get diagnostics
    diagnostics = strategy.get_signal_diagnostics(df_features)
    
    return df_features, diagnostics


def compute_signal_metrics(df: pd.DataFrame, pair: str) -> Dict:
    """
    Compute performance metrics for generated signals.
    
    Args:
        df: DataFrame with signals and returns
        pair: Pair name
        
    Returns:
        Dict of metrics
    """
    # Returns
    if 'returns' not in df.columns:
        df['returns'] = df['close'].pct_change()
    
    # Forward returns (1-bar ahead)
    df['forward_returns'] = df['returns'].shift(-1)
    
    # Strategy returns (signal × forward_returns, no lag needed now that look-ahead is fixed)
    df['strategy_returns'] = df['signal'] * df['forward_returns']
    
    # Remove NaNs
    valid = df[['signal', 'forward_returns', 'strategy_returns']].dropna()
    
    if len(valid) == 0:
        return {
            'pair': pair,
            'n_signals': 0,
            'n_long': 0,
            'n_short': 0,
            'ic': np.nan,
            'ic_tstat_hac': np.nan,
            'ic_pvalue': np.nan,
            'sharpe': np.nan,
            'mean_return': np.nan,
            'win_rate': np.nan,
            'is_stationary': False
        }
    
    # Signal counts
    n_signals = (valid['signal'] != 0).sum()
    n_long = (valid['signal'] == 1).sum()
    n_short = (valid['signal'] == -1).sum()
    
    # IC (only on signal days)
    signal_days = valid[valid['signal'] != 0]
    if len(signal_days) > 10:
        ic = compute_information_coefficient(
            signal_days['signal'],
            signal_days['forward_returns']
        )
        ic_tstat_hac, ic_pvalue = compute_hac_tstat(
            signal_days['signal'],
            signal_days['forward_returns']
        )
    else:
        ic, ic_tstat_hac, ic_pvalue = np.nan, np.nan, 1.0
    
    # Strategy performance
    strategy_returns = valid['strategy_returns']
    mean_return = strategy_returns.mean()
    std_return = strategy_returns.std()
    sharpe = mean_return / std_return * np.sqrt(252 * 24) if std_return > 0 else 0  # Hourly to annual
    
    # Win rate (on signal days only)
    if len(signal_days) > 0:
        win_rate = (signal_days['strategy_returns'] > 0).sum() / len(signal_days)
    else:
        win_rate = np.nan
    
    # Stationarity of returns
    is_stationary, _, _ = test_stationarity(strategy_returns)
    
    return {
        'pair': pair,
        'n_signals': n_signals,
        'n_long': n_long,
        'n_short': n_short,
        'ic': ic,
        'ic_tstat_hac': ic_tstat_hac,
        'ic_pvalue': ic_pvalue,
        'sharpe': sharpe,
        'mean_return': mean_return * 10000,  # bps
        'win_rate': win_rate,
        'is_stationary': is_stationary
    }


def validate_cross_pair_consistency(results: pd.DataFrame) -> Dict:
    """
    Check consistency across pairs.
    
    Args:
        results: DataFrame with per-pair metrics
        
    Returns:
        Dict of consistency metrics
    """
    # IC sign consistency
    ic_positive = (results['ic'] > 0).sum()
    ic_negative = (results['ic'] < 0).sum()
    ic_valid = results['ic'].notna().sum()
    ic_consistency = max(ic_positive, ic_negative) / ic_valid if ic_valid > 0 else 0
    
    # Win rate consistency (should be > 50% for most pairs)
    win_rate_above_50 = (results['win_rate'] > 0.5).sum()
    win_rate_valid = results['win_rate'].notna().sum()
    win_rate_consistency = win_rate_above_50 / win_rate_valid if win_rate_valid > 0 else 0
    
    # Sharpe consistency (positive for most pairs)
    sharpe_positive = (results['sharpe'] > 0).sum()
    sharpe_valid = results['sharpe'].notna().sum()
    sharpe_consistency = sharpe_positive / sharpe_valid if sharpe_valid > 0 else 0
    
    # Statistical significance
    sig_pairs = (results['ic_pvalue'] < 0.05).sum()
    sig_ratio = sig_pairs / len(results)
    
    return {
        'ic_consistency': ic_consistency,
        'win_rate_consistency': win_rate_consistency,
        'sharpe_consistency': sharpe_consistency,
        'significant_pairs': sig_pairs,
        'significance_ratio': sig_ratio,
        'mean_ic': results['ic'].mean(),
        'median_sharpe': results['sharpe'].median(),
        'mean_win_rate': results['win_rate'].mean()
    }


def main():
    """Run cross-pair validation."""
    print("="*80)
    print("EXHAUSTION-FAILURE STRATEGY: CROSS-PAIR VALIDATION")
    print("="*80)
    
    # Paths
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "raw"
    config_path = project_root / "config" / "config.yaml"
    
    # Load all pairs
    print("\n1. Loading FX pairs...")
    pairs_data = load_all_pairs(data_dir)
    print(f"\nLoaded {len(pairs_data)} pairs")
    
    # Initialize strategy
    strategy = ExhaustionFailureStrategy.from_config(str(config_path))
    print(f"\n2. Strategy Configuration:")
    print(f"   Range expansion threshold: {strategy.range_expansion_threshold}")
    print(f"   Extreme zone thresholds: {strategy.extreme_zone_upper}, {strategy.extreme_zone_lower}")
    print(f"   Consecutive bars required: {strategy.consecutive_bars_required}")
    
    # Test on each pair
    print("\n3. Testing strategy on all pairs...")
    print("-"*80)
    
    results = []
    for pair, df in pairs_data.items():
        print(f"\nTesting {pair}...")
        
        try:
            # Generate signals
            df_signals, diagnostics = generate_strategy_signals(df, strategy)
            
            # Compute metrics
            metrics = compute_signal_metrics(df_signals, pair)
            metrics.update(diagnostics)
            
            results.append(metrics)
            
            # Print summary
            print(f"  Exhaustion detections: {diagnostics['total_exhaustion']}")
            print(f"  Signal count: {metrics['n_signals']} (Long: {metrics['n_long']}, Short: {metrics['n_short']})")
            print(f"  IC: {metrics['ic']:.4f}, t-stat: {metrics['ic_tstat_hac']:.2f}, p-value: {metrics['ic_pvalue']:.4f}")
            print(f"  Win rate: {metrics['win_rate']:.2%}, Sharpe: {metrics['sharpe']:.2f}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Check consistency
    print("\n4. Cross-Pair Consistency Analysis...")
    print("-"*80)
    consistency = validate_cross_pair_consistency(results_df)
    
    print(f"\nIC sign consistency: {consistency['ic_consistency']:.1%}")
    print(f"Win rate consistency (>50%): {consistency['win_rate_consistency']:.1%}")
    print(f"Sharpe sign consistency (>0): {consistency['sharpe_consistency']:.1%}")
    print(f"Statistically significant pairs: {consistency['significant_pairs']}/{len(results_df)} ({consistency['significance_ratio']:.1%})")
    print(f"\nMean IC: {consistency['mean_ic']:.4f}")
    print(f"Median Sharpe: {consistency['median_sharpe']:.2f}")
    print(f"Mean win rate: {consistency['mean_win_rate']:.2%}")
    
    # Summary table
    print("\n5. Summary by Pair:")
    print("-"*80)
    summary_cols = ['pair', 'n_signals', 'ic', 'ic_tstat_hac', 'win_rate', 'sharpe', 'mean_return']
    print(results_df[summary_cols].to_string(index=False))
    
    # Save results
    output_dir = project_root / "reports"
    output_dir.mkdir(exist_ok=True)
    results_df.to_csv(output_dir / "cross_pair_validation.csv", index=False)
    print(f"\n✓ Results saved to {output_dir / 'cross_pair_validation.csv'}")
    
    # Overall assessment
    print("\n" + "="*80)
    print("OVERALL ASSESSMENT")
    print("="*80)
    
    if consistency['win_rate_consistency'] >= 0.7 and consistency['mean_win_rate'] >= 0.6:
        print("✓ PASS: Strategy shows strong consistency across pairs")
        print(f"  {int(consistency['win_rate_consistency']*100)}% of pairs have win rate > 50%")
        print(f"  Mean win rate: {consistency['mean_win_rate']:.1%}")
    else:
        print("✗ CAUTION: Strategy shows inconsistent performance")
        print(f"  Only {int(consistency['win_rate_consistency']*100)}% of pairs have win rate > 50%")
        print(f"  Mean win rate: {consistency['mean_win_rate']:.1%} (target: >60%)")
    
    print("\n" + "="*80)
    
    return results_df, consistency


if __name__ == "__main__":
    results_df, consistency = main()
