"""
Quick test of multi-timeframe features module.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.features.multi_timeframe import MultiTimeframeFeatures

def main():
    print("Quick MTF Test")
    print("="*50)
    
    # Load NZDJPY
    loader = FXDataLoader()
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    csv_path = data_dir / 'NZDJPY60.csv'
    
    df, _ = loader.load_csv(str(csv_path), pair='NZDJPY')
    print(f"Loaded {len(df)} bars")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Index type: {type(df.index)}")
    
    # Add MTF features
    mtf = MultiTimeframeFeatures()
    print("\nAdding MTF features...")
    
    df_mtf = mtf.add_higher_tf_features(df)
    print(f"✅ Done! New columns: {[c for c in df_mtf.columns if c not in df.columns]}")
    
    # Check a few rows
    print("\n Sample data:")
    print(df_mtf[['close', 'h4_trend', 'h4_adx', 'd1_trend', 'd1_adx']].tail(10))
    
    # Report
    report = mtf.generate_report(df_mtf)
    print("\n📊 Report:")
    for key, value in report.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
