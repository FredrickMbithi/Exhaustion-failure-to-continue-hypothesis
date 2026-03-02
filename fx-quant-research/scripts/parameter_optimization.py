"""
Parameter Optimization for Exhaustion-Failure Strategy

Days 22-24: Grid search to find optimal parameters that:
- Increase win rate to 60%+
- Reduce signal rate to <5%
- Maintain statistical significance
"""

import sys
from pathlib import Path
from itertools import product
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
from scipy.stats import spearmanr


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all required features to dataframe."""
    fe = FeatureEngineering()
    df = fe.add_momentum(df, windows=[5, 10, 20])
    df = fe.add_volatility_features(df)
    df = fe.add_range_features(df, windows=[10, 20, 50])
    df = fe.add_close_position(df)
    df = fe.add_consecutive_direction(df, windows=[2, 3])
    df = fe.add_range_breakout_features(df, windows=[10, 20, 50])
    return df


def test_parameters(
    df: pd.DataFrame,
    pair: str,
    range_expansion: float,
    extreme_upper: float,
    extreme_lower: float,
    consecutive_bars: int
) -> Dict:
    """Test a single parameter combination."""
    
    # Create strategy with these parameters
    strategy = ExhaustionFailureStrategy(
        range_expansion_threshold=range_expansion,
        median_range_window=20,
        extreme_zone_upper=extreme_upper,
        extreme_zone_lower=extreme_lower,
        consecutive_bars_required=consecutive_bars,
        enable_failure_filter=True
    )
    
    # Generate signals
    df_test = df.copy()
    df_test['signal'] = strategy.generate_signals(df_test)
    
    # Get diagnostics
    diagnostics = strategy.get_signal_diagnostics(df_test)
    
    # Calculate returns
    df_test['returns'] = df_test['close'].pct_change()
    df_test['forward_returns'] = df_test['returns'].shift(-1)
    df_test['strategy_returns'] = df_test['signal'] * df_test['forward_returns']
    
    # Metrics
    valid = df_test[['signal', 'forward_returns', 'strategy_returns']].dropna()
    signal_days = valid[valid['signal'] != 0]
    
    n_signals = len(signal_days)
    n_long = (signal_days['signal'] == 1).sum()
    n_short = (signal_days['signal'] == -1).sum()
    
    if n_signals > 10:  # Need minimum signals for valid statistics
        win_rate = (signal_days['strategy_returns'] > 0).mean()
        mean_return = signal_days['strategy_returns'].mean()
        std_return = signal_days['strategy_returns'].std()
        sharpe = mean_return / std_return * (252 * 24)**0.5 if std_return > 0 else 0
        
        # IC
        ic, ic_pval = spearmanr(signal_days['signal'], signal_days['forward_returns'])
    else:
        win_rate = 0
        mean_return = 0
        sharpe = 0
        ic = 0
        ic_pval = 1.0
    
    return {
        'pair': pair,
        'range_expansion': range_expansion,
        'extreme_upper': extreme_upper,
        'extreme_lower': extreme_lower,
        'consecutive_bars': consecutive_bars,
        'bars': len(df),
        'exhaustions': diagnostics['total_exhaustion'],
        'signals': n_signals,
        'n_long': n_long,
        'n_short': n_short,
        'signal_rate': n_signals / len(df) * 100,
        'win_rate': win_rate * 100,
        'mean_return': mean_return,
        'sharpe': sharpe,
        'ic': ic,
        'ic_pval': ic_pval,
        'reduction_ratio': diagnostics['reduction_ratio']
    }


def optimize_pair(
    pair: str,
    data_dir: Path,
    param_grid: Dict[str, List]
) -> pd.DataFrame:
    """Run parameter optimization for a single pair."""
    
    print(f"\n{'='*60}")
    print(f"Optimizing {pair}")
    print(f"{'='*60}")
    
    # Load data
    csv_path = data_dir / f"{pair}60.csv"
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return pd.DataFrame()
    
    try:
        loader = FXDataLoader()
        df, metadata = loader.load_csv(str(csv_path), pair)
        print(f"✅ Loaded {len(df)} bars")
        
        # Add features once
        df = add_features(df)
        
    except Exception as e:
        print(f"❌ Error loading {pair}: {e}")
        return pd.DataFrame()
    
    # Generate parameter combinations
    param_combinations = list(product(
        param_grid['range_expansion'],
        param_grid['extreme_upper'],
        param_grid['extreme_lower'],
        param_grid['consecutive_bars']
    ))
    
    total = len(param_combinations)
    print(f"\nTesting {total} parameter combinations...")
    
    results = []
    for i, (range_exp, ext_upper, ext_lower, consec) in enumerate(param_combinations, 1):
        if i % 10 == 0 or i == total:
            print(f"  Progress: {i}/{total} ({i/total*100:.1f}%)", end='\r')
        
        result = test_parameters(
            df, pair, range_exp, ext_upper, ext_lower, consec
        )
        results.append(result)
    
    print(f"\n✅ Completed {total} tests")
    
    return pd.DataFrame(results)


def analyze_results(df_results: pd.DataFrame) -> None:
    """Analyze optimization results and identify best parameters."""
    
    print(f"\n{'='*60}")
    print("OPTIMIZATION RESULTS ANALYSIS")
    print(f"{'='*60}")
    
    # Filter to valid results (minimum 20 signals)
    valid = df_results[df_results['signals'] >= 20].copy()
    
    if len(valid) == 0:
        print("❌ No parameter combinations generated enough signals")
        return
    
    print(f"\nValid combinations: {len(valid)} (with ≥20 signals)")
    
    # Goal 1: Win rate ≥ 60%
    high_wr = valid[valid['win_rate'] >= 60.0]
    print(f"\nGoal 1: Win rate ≥ 60%")
    print(f"  Achieving: {len(high_wr)} combinations ({len(high_wr)/len(valid)*100:.1f}%)")
    
    # Goal 2: Signal rate < 5%
    low_sig = valid[valid['signal_rate'] < 5.0]
    print(f"\nGoal 2: Signal rate < 5%")
    print(f"  Achieving: {len(low_sig)} combinations ({len(low_sig)/len(valid)*100:.1f}%)")
    
    # Goal 3: IC > 0.2 with p < 0.05
    strong_ic = valid[(valid['ic'] > 0.2) & (valid['ic_pval'] < 0.05)]
    print(f"\nGoal 3: IC > 0.2 with p < 0.05")
    print(f"  Achieving: {len(strong_ic)} combinations ({len(strong_ic)/len(valid)*100:.1f}%)")
    
    # Combined goals
    all_goals = valid[
        (valid['win_rate'] >= 60.0) &
        (valid['signal_rate'] < 5.0) &
        (valid['ic'] > 0.2) &
        (valid['ic_pval'] < 0.05)
    ]
    
    print(f"\n🎯 ALL GOALS MET:")
    print(f"  {len(all_goals)} combinations ({len(all_goals)/len(valid)*100:.1f}%)")
    
    if len(all_goals) > 0:
        print(f"\n{'='*60}")
        print("TOP PARAMETER SETS (Meeting All Goals)")
        print(f"{'='*60}")
        
        # Sort by composite score
        all_goals['score'] = (
            all_goals['win_rate'] * 0.4 +
            (100 - all_goals['signal_rate']) * 0.2 +
            all_goals['ic'] * 100 * 0.3 +
            all_goals['sharpe'] * 0.1
        )
        
        top = all_goals.nlargest(10, 'score')
        
        print("\n" + top[[
            'pair', 'range_expansion', 'extreme_upper', 'extreme_lower', 
            'consecutive_bars', 'win_rate', 'signal_rate', 'ic', 'signals', 'score'
        ]].to_string(index=False))
        
    else:
        print(f"\n{'='*60}")
        print("BEST COMPROMISE PARAMETERS")
        print(f"{'='*60}")
        
        # Relaxed criteria
        relaxed = valid[
            (valid['win_rate'] >= 55.0) &
            (valid['signal_rate'] < 10.0) &
            (valid['ic'] > 0.1) &
            (valid['ic_pval'] < 0.05)
        ]
        
        if len(relaxed) > 0:
            print(f"\nRelaxed goals met: {len(relaxed)} combinations")
            
            relaxed['score'] = (
                relaxed['win_rate'] * 0.4 +
                (100 - relaxed['signal_rate']) * 0.2 +
                relaxed['ic'] * 100 * 0.3 +
                relaxed['sharpe'] * 0.1
            )
            
            top = relaxed.nlargest(10, 'score')
            
            print("\n" + top[[
                'pair', 'range_expansion', 'extreme_upper', 'extreme_lower',
                'consecutive_bars', 'win_rate', 'signal_rate', 'ic', 'signals', 'score'
            ]].to_string(index=False))
        else:
            print("\n❌ No combinations meet even relaxed criteria")
            
            # Show best by individual metrics
            print("\nBest by Win Rate:")
            print(valid.nlargest(3, 'win_rate')[[
                'range_expansion', 'extreme_upper', 'extreme_lower',
                'consecutive_bars', 'win_rate', 'signal_rate', 'ic', 'signals'
            ]].to_string(index=False))
            
            print("\nBest by IC:")
            print(valid.nlargest(3, 'ic')[[
                'range_expansion', 'extreme_upper', 'extreme_lower',
                'consecutive_bars', 'win_rate', 'signal_rate', 'ic', 'signals'
            ]].to_string(index=False))
    
    # Parameter sensitivity analysis
    print(f"\n{'='*60}")
    print("PARAMETER SENSITIVITY ANALYSIS")
    print(f"{'='*60}")
    
    for param in ['range_expansion', 'extreme_upper', 'extreme_lower', 'consecutive_bars']:
        print(f"\n{param.replace('_', ' ').title()}:")
        grouped = valid.groupby(param).agg({
            'win_rate': 'mean',
            'signal_rate': 'mean',
            'ic': 'mean',
            'signals': 'mean'
        }).round(2)
        print(grouped.to_string())


def main():
    """Main optimization routine."""
    
    print("="*60)
    print("EXHAUSTION-FAILURE STRATEGY PARAMETER OPTIMIZATION")
    print("Days 22-24: Finding Optimal Parameters")
    print("="*60)
    
    # Define parameter grid
    param_grid = {
        'range_expansion': [0.8, 1.0, 1.2, 1.5, 2.0],  # Baseline: 0.8
        'extreme_upper': [0.65, 0.70, 0.75, 0.80, 0.85],  # Baseline: 0.65
        'extreme_lower': [0.35, 0.30, 0.25, 0.20, 0.15],  # Baseline: 0.35
        'consecutive_bars': [2, 3, 4]  # Baseline: 2
    }
    
    print(f"\nParameter Grid:")
    print(f"  Range Expansion: {param_grid['range_expansion']}")
    print(f"  Extreme Upper: {param_grid['extreme_upper']}")
    print(f"  Extreme Lower: {param_grid['extreme_lower']}")
    print(f"  Consecutive Bars: {param_grid['consecutive_bars']}")
    print(f"\nTotal combinations: {np.prod([len(v) for v in param_grid.values()])}")
    
    # Test pairs
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    pairs = ["USDJPY", "NZDJPY"]
    
    all_results = []
    
    for pair in pairs:
        df_results = optimize_pair(pair, data_dir, param_grid)
        if not df_results.empty:
            all_results.append(df_results)
    
    if not all_results:
        print("\n❌ No results generated")
        return
    
    # Combine results
    df_all = pd.concat(all_results, ignore_index=True)
    
    # Save raw results
    output_file = Path(__file__).parent.parent / "parameter_optimization_results.csv"
    df_all.to_csv(output_file, index=False)
    print(f"\n✅ Raw results saved to: {output_file.name}")
    
    # Analysis
    analyze_results(df_all)
    
    # Save top parameters
    valid = df_all[df_all['signals'] >= 20].copy()
    if len(valid) > 0:
        valid['score'] = (
            valid['win_rate'] * 0.4 +
            (100 - valid['signal_rate']) * 0.2 +
            valid['ic'] * 100 * 0.3 +
            valid['sharpe'] * 0.1
        )
        
        top_params = valid.nlargest(20, 'score')
        top_file = Path(__file__).parent.parent / "top_parameters.csv"
        top_params.to_csv(top_file, index=False)
        print(f"✅ Top 20 parameter sets saved to: {top_file.name}")
    
    print(f"\n{'='*60}")
    print("OPTIMIZATION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
