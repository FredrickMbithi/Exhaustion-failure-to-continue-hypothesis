"""Simple validation runner to generate summary results."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
import pandas as pd

def main():
    print("="*60)
    print("Cross-Pair Validation - Fixed Strategy (No Look-Ahead)")
    print("="*60)
    
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    loader = FXDataLoader()
    strategy = ExhaustionFailureStrategy.from_config("config/config.yaml")
    fe = FeatureEngineering()
    
    pairs = ["EURCHF", "GBPUSD", "AUDNZD"]  # Test on 3 large pairs
    
    results = []
    
    for pair in pairs:
        print(f"\nProcessing {pair}...")
        
        csv_path = data_dir / f"{pair}60.csv"
        if not csv_path.exists():
            continue
        
        try:
            df, _ = loader.load_csv(str(csv_path), pair)
            
            # Add features
            df = fe.add_momentum(df, windows=[5, 10, 20])
            df = fe.add_volatility_features(df)
            df = fe.add_range_features(df, windows=[10, 20, 50])
            df = fe.add_close_position(df)
            df = fe.add_consecutive_direction(df, windows=[2, 3])
            df = fe.add_range_breakout_features(df, windows=[10, 20, 50])
            
            # Generate signals
            df['signal'] = strategy.generate_signals(df)
            
            # Calculate returns
            df['returns'] = df['close'].pct_change()
            df['forward_returns'] = df['returns'].shift(-1)
            df['strategy_returns'] = df['signal'] * df['forward_returns']
            
            # Remove NaNs
            valid = df[['signal', 'forward_returns', 'strategy_returns']].dropna()
            
            # Metrics
            signal_days = valid[valid['signal'] != 0]
            n_signals = len(signal_days)
            
            if n_signals > 0:
                win_rate = (signal_days['strategy_returns'] > 0).mean()
                mean_return = signal_days['strategy_returns'].mean()
                sharpe = mean_return / signal_days['strategy_returns'].std() * (252 * 24)**0.5 if signal_days['strategy_returns'].std() > 0 else 0
                
                results.append({
                    'pair': pair,
                    'n_signals': n_signals,
                    'win_rate': win_rate,
                    'mean_return': mean_return,
                    'sharpe': sharpe
                })
                
                print(f"  Signals: {n_signals}")
                print(f"  Win Rate: {win_rate*100:.2f}%")
                print(f"  Mean Return: {mean_return:.6f}")
                print(f"  Sharpe: {sharpe:.2f}")
            
        except Exception as e:
            print(f"  Error: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    df_results = pd.DataFrame(results)
    print(f"\nMean Win Rate: {df_results['win_rate'].mean()*100:.2f}%")
    print(f"Mean Sharpe: {df_results['sharpe'].mean():.2f}")
    print(f"Total Signals: {df_results['n_signals'].sum()}")
    
    # Save
    output_file = Path(__file__).parent.parent / "cross_pair_validation_fixed.csv"
    df_results.to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
