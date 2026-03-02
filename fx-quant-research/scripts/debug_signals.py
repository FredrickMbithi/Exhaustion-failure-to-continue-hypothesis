"""Debug signal generation to identify win rate issue."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.library import FeatureEngineering
from src.data.loader import FXDataLoader


def debug_signal_logic():
    """Examine signal generation and returns calculation in detail."""
    
    # Load small dataset
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    loader = FXDataLoader()
    
    pairs_to_test = ["GBPUSD", "EURCHF"]  # Use pairs with lots of data
    
    for pair in pairs_to_test:
        print(f"\n{'='*60}")
        print(f"Debugging {pair}")
        print(f"{'='*60}\n")
        
        csv_path = data_dir / f"{pair}60.csv"
        if not csv_path.exists():
            print(f"File not found: {csv_path}")
            continue
        
        try:
            df, metadata = loader.load_csv(str(csv_path), pair)
            print(f"Loaded {len(df)} bars")
        except Exception as e:
            print(f"Error loading {pair}: {e}")
            continue
        
        # Take just first 5000 bars for speed
        df = df.head(5000)
        
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
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['forward_returns'] = df['returns'].shift(-1)  # Next bar's return
        
        # Find signal bars
        signal_bars = df[df['signal'] != 0].copy()
        
        if len(signal_bars) == 0:
            print("No signals generated!")
            continue
        
        print(f"\nTotal signals: {len(signal_bars)}")
        print(f"Long signals: {(signal_bars['signal'] == 1).sum()}")
        print(f"Short signals: {(signal_bars['signal'] == -1).sum()}")
        
        # Look at first 10 signal examples
        print(f"\n{'='*60}")
        print("First 10 Signal Examples:")
        print(f"{'='*60}")
        
        for idx, (i, row) in enumerate(signal_bars.head(10).iterrows()):
            print(f"\nSignal {idx+1} at index {i}:")
            print(f"  Signal: {row['signal']} ({'LONG' if row['signal'] == 1 else 'SHORT'})")
            print(f"  Close: {row['close']:.5f}")
            print(f"  Forward return: {row['forward_returns']:.6f} ({row['forward_returns']*100:.2f}%)")
            
            # Calculate strategy return (what we would get)
            strategy_return = row['signal'] * row['forward_returns']
            print(f"  Strategy return: {strategy_return:.6f} ({strategy_return*100:.2f}%)")
            print(f"  Result: {'WIN' if strategy_return > 0 else 'LOSS'}")
        
        # Overall statistics
        print(f"\n{'='*60}")
        print("Overall Signal Statistics:")
        print(f"{'='*60}")
        
        # Method 1: Immediate returns (no lag)
        signal_bars['strategy_return_immediate'] = signal_bars['signal'] * signal_bars['forward_returns']
        win_rate_immediate = (signal_bars['strategy_return_immediate'] > 0).mean()
        print(f"\nMethod 1 (Immediate - No Lag):")
        print(f"  Win rate: {win_rate_immediate*100:.2f}%")
        print(f"  Mean return: {signal_bars['strategy_return_immediate'].mean():.6f}")
        
        # Method 2: With 1-bar lag (as in validation script)
        df['strategy_return_lagged'] = df['signal'].shift(1) * df['forward_returns']
        signal_bars_lagged = df[df['signal'].shift(1) != 0].copy()
        win_rate_lagged = (signal_bars_lagged['strategy_return_lagged'] > 0).mean()
        print(f"\nMethod 2 (1-Bar Lagged - As in Validation):")
        print(f"  Win rate: {win_rate_lagged*100:.2f}%")
        print(f"  Mean return: {signal_bars_lagged['strategy_return_lagged'].mean():.6f}")
        
        # Method 3: Inverted signals (test hypothesis)
        signal_bars['strategy_return_inverted'] = -signal_bars['signal'] * signal_bars['forward_returns']
        win_rate_inverted = (signal_bars['strategy_return_inverted'] > 0).mean()
        print(f"\nMethod 3 (INVERTED SIGNALS - Test Hypothesis):")
        print(f"  Win rate: {win_rate_inverted*100:.2f}%")
        print(f"  Mean return: {signal_bars['strategy_return_inverted'].mean():.6f}")
        
        # Check correlation
        signal_fwd_corr = signal_bars['signal'].corr(signal_bars['forward_returns'])
        print(f"\nCorrelation Analysis:")
        print(f"  Signal vs Forward Returns: {signal_fwd_corr:.4f}")
        print(f"  (Positive correlation with low win rate suggests timing/lag issue)")
        
        # Look at exhaustion detection
        bulls, bears = strategy.detect_exhaustion(df)
        bull_fail, bear_fail = strategy.detect_failure_to_continue(df, bulls, bears)
        
        print(f"\nExhaustion Diagnostics:")
        print(f"  Bullish exhaustions: {bulls.sum()}")
        print(f"  Bearish exhaustions: {bears.sum()}")
        print(f"  Bullish failures (SHORT signals): {bull_fail.sum()}")
        print(f"  Bearish failures (LONG signals): {bear_fail.sum()}")
        print(f"  Reduction ratio: {(bull_fail.sum() + bear_fail.sum()) / (bulls.sum() + bears.sum()) * 100:.1f}%")


if __name__ == "__main__":
    debug_signal_logic()
