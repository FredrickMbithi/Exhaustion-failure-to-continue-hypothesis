"""Test USDJPY and NZDJPY with fixed strategy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
import pandas as pd

def test_pair(pair: str, data_dir: Path):
    """Test a single pair and return results."""
    print(f"\n{'='*60}")
    print(f"Testing {pair}")
    print(f"{'='*60}")
    
    csv_path = data_dir / f"{pair}60.csv"
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return None
    
    try:
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
        
        # Generate signals
        strategy = ExhaustionFailureStrategy.from_config("config/config.yaml")
        df['signal'] = strategy.generate_signals(df)
        
        # Get diagnostics
        diagnostics = strategy.get_signal_diagnostics(df)
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['forward_returns'] = df['returns'].shift(-1)
        df['strategy_returns'] = df['signal'] * df['forward_returns']
        
        # Metrics
        valid = df[['signal', 'forward_returns', 'strategy_returns']].dropna()
        signal_days = valid[valid['signal'] != 0]
        
        n_signals = len(signal_days)
        n_long = (signal_days['signal'] == 1).sum()
        n_short = (signal_days['signal'] == -1).sum()
        
        if n_signals > 0:
            win_rate = (signal_days['strategy_returns'] > 0).mean()
            mean_return = signal_days['strategy_returns'].mean()
            std_return = signal_days['strategy_returns'].std()
            sharpe = mean_return / std_return * (252 * 24)**0.5 if std_return > 0 else 0
            
            # Calculate IC
            from scipy.stats import spearmanr
            ic, ic_pval = spearmanr(signal_days['signal'], signal_days['forward_returns'])
        else:
            win_rate = 0
            mean_return = 0
            sharpe = 0
            ic = 0
            ic_pval = 1.0
        
        # Print results
        print(f"\n📊 Signal Generation:")
        print(f"  Total bars: {len(df)}")
        print(f"  Bullish exhaustions: {diagnostics['bullish_exhaustion']}")
        print(f"  Bearish exhaustions: {diagnostics['bearish_exhaustion']}")
        print(f"  Total exhaustions: {diagnostics['total_exhaustion']}")
        print(f"  Signals after filter: {diagnostics['total_signals']}")
        print(f"  Reduction ratio: {diagnostics['reduction_ratio']:.1%}")
        
        print(f"\n📈 Signal Distribution:")
        print(f"  Long signals: {n_long}")
        print(f"  Short signals: {n_short}")
        print(f"  Total signals: {n_signals}")
        print(f"  Signal rate: {n_signals/len(df)*100:.2f}% of bars")
        
        print(f"\n💰 Performance (No Look-Ahead):")
        print(f"  Win rate: {win_rate*100:.2f}%")
        print(f"  Mean return per signal: {mean_return:.6f} ({mean_return*10000:.2f} bps)")
        print(f"  Sharpe ratio (annualized): {sharpe:.2f}")
        print(f"  Information Coefficient: {ic:.4f}")
        print(f"  IC p-value: {ic_pval:.4f}")
        
        return {
            'pair': pair,
            'bars': len(df),
            'exhaustions': diagnostics['total_exhaustion'],
            'signals': n_signals,
            'long': n_long,
            'short': n_short,
            'signal_rate': n_signals/len(df)*100,
            'win_rate': win_rate*100,
            'mean_return': mean_return,
            'sharpe': sharpe,
            'ic': ic,
            'ic_pval': ic_pval,
            'reduction_ratio': diagnostics['reduction_ratio']
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("="*60)
    print("USDJPY and NZDJPY Strategy Test")
    print("Post Look-Ahead Bias Fix")
    print("="*60)
    
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    pairs = ["USDJPY", "NZDJPY"]
    
    results = []
    for pair in pairs:
        result = test_pair(pair, data_dir)
        if result:
            results.append(result)
    
    # Summary
    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        df_results = pd.DataFrame(results)
        print("\n" + df_results.to_string(index=False))
        
        print(f"\n📊 Aggregate Statistics:")
        print(f"  Mean Win Rate: {df_results['win_rate'].mean():.2f}%")
        print(f"  Mean Sharpe: {df_results['sharpe'].mean():.2f}")
        print(f"  Mean IC: {df_results['ic'].mean():.4f}")
        print(f"  Mean Signal Rate: {df_results['signal_rate'].mean():.2f}%")
        print(f"  Total Signals: {df_results['signals'].sum()}")
        
        # Save
        output_file = Path(__file__).parent.parent / "test_usdjpy_nzdjpy_results.csv"
        df_results.to_csv(output_file, index=False)
        print(f"\n✅ Results saved to: {output_file.name}")
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)


if __name__ == "__main__":
    main()
