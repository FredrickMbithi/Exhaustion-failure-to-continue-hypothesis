"""Quick test to verify all components work together."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import yaml

from src.data.loader import FXDataLoader
from src.features.library import FeatureEngineering
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy

def test_single_pair():
    """Test strategy on NZDJPY."""
    print("Testing exhaustion-failure strategy on NZDJPY...\n")
    
    # Load data
    loader = FXDataLoader()
    df, metadata = loader.load_csv("data/raw/NZDJPY60.csv", pair="NZDJPY")
    print(f"✓ Loaded {len(df)} bars")
    
    # Add features
    fe = FeatureEngineering()
    df_features = df.copy()
    df_features = fe.add_momentum(df_features, windows=[5, 10, 20])
    df_features = fe.add_volatility_features(df_features)
    df_features = fe.add_range_features(df_features, windows=[10, 20, 50])
    df_features = fe.add_close_position(df_features)
    df_features = fe.add_consecutive_direction(df_features, windows=[2, 3])
    df_features = fe.add_range_breakout_features(df_features, windows=[10, 20, 50])
    print(f"✓ Generated {len(df_features.columns)} features")
    
    # Create strategy from config
    strategy = ExhaustionFailureStrategy.from_config("config/config.yaml")
    print(f"✓ Initialized strategy (threshold: {strategy.range_expansion_threshold})")
    
    # Generate signals
    signals = strategy.generate_signals(df_features)
    diagnostics = strategy.get_signal_diagnostics(df_features)
    
    print(f"\n✓ Generated {diagnostics['total_signals']} signals from {diagnostics['total_exhaustion']} exhaustions")
    print(f"  - Long signals: {diagnostics['bullish_failure']}")
    print(f"  - Short signals: {diagnostics['bearish_failure']}")
    print(f"  - Reduction ratio: {diagnostics['reduction_ratio']:.2%}")
    print(f"  - Reduction ratio: {diagnostics['reduction_ratio']:.2%}")
    
    # Show signal dates
    signal_dates = df_features[signals != 0].head(10)
    if len(signal_dates) > 0:
        print(f"\nFirst 5 signals:")
        for idx, row in signal_dates.head(5).iterrows():
            direction = "LONG" if signals.loc[idx] == 1 else "SHORT"
            print(f"  {idx}: {direction} @ {row['close']:.4f}")
    
    print("\n✓ All components working correctly!")
    return True

if __name__ == "__main__":
    try:
        test_single_pair()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
