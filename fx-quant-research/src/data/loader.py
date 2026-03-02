"""
FX data loader with robust validation and timezone handling.

This module provides the FXDataLoader class for loading historical OHLC data
from CSV files with proper UTC timezone normalization, duplicate detection,
and monotonic time index enforcement.
"""

import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


class FXDataLoader:
    """
    Load and validate FX OHLC data from CSV files.
    
    Enforces:
    - UTC timezone normalization
    - Chronological sorting
    - Duplicate detection
    - Monotonic time index
    - Required column validation
    
    Examples:
        >>> loader = FXDataLoader()
        >>> df, metadata = loader.load_csv("data/raw/eurusd.csv", pair="EURUSD")
        >>> print(f"Loaded {len(df)} bars for {metadata['pair']}")
    """
    
    REQUIRED_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    OPTIONAL_COLUMNS = ['spread']
    
    def __init__(self):
        """Initialize FX data loader."""
        pass
    
    def load_csv(
        self,
        path: Optional[str] = None,
        pair: str = 'EURUSD',
        timestamp_column: str = 'timestamp',
        has_header: bool = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Load FX OHLC data from CSV file.
        
        Args:
            path: Path to CSV file. If None, uses CLI argument or raises error
            pair: Currency pair name (e.g., 'EURUSD')
            timestamp_column: Name of timestamp column in CSV
            has_header: Whether CSV has header row. If None, auto-detect.
            
        Returns:
            Tuple of (DataFrame with DatetimeIndex, metadata dict)
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            DataValidationError: If data validation fails
            ValueError: If required columns missing
            
        Examples:
            >>> loader = FXDataLoader()
            >>> df, meta = loader.load_csv("data/raw/eurusd.csv", "EURUSD")
            >>> assert df.index.tz.zone == 'UTC'
            >>> assert df.index.is_monotonic_increasing
        """
        if path is None:
            parser = argparse.ArgumentParser()
            parser.add_argument('--data-path', type=str, help='Path to CSV data file')
            args, _ = parser.parse_known_args()
            if args.data_path:
                path = args.data_path
            else:
                raise ValueError("No data path specified. Provide path argument or use --data-path CLI flag")
        
        csv_path = Path(path)
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        # Read CSV with explicit dtypes
        dtype_dict = {
            'open': np.float64,
            'high': np.float64,
            'low': np.float64,
            'close': np.float64,
            'volume': np.float64,
        }
        
        # Auto-detect header if not specified
        if has_header is None:
            # Try reading first line to detect if it has column names
            try:
                test_df = pd.read_csv(csv_path, nrows=1)
                # If first row looks like data (all numeric except first col), no header
                has_header = not all(col.replace('.', '').replace('-', '').replace(':', '').isdigit() 
                                    or col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                                    for col in test_df.columns)
            except:
                has_header = True
        
        # Define column names for headerless CSVs
        if not has_header:
            # MT4/MT5 format: date, time, open, high, low, close, volume
            df = pd.read_csv(csv_path, names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
            # Combine date and time into a single timestamp column
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df = df.drop(['date', 'time'], axis=1)
        else:
            # Read with headers
            df = pd.read_csv(csv_path)
            
        # Check if spread column exists
        if 'spread' in df.columns:
            dtype_dict['spread'] = np.float64
        
        # Convert dtypes
        for col, dtype in dtype_dict.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype)
        
        # Validate required columns
        missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}. Found: {list(df.columns)}")
        
        # Convert timestamp to UTC DatetimeIndex
        try:
            df[timestamp_column] = pd.to_datetime(df[timestamp_column], utc=True)
        except Exception as e:
            raise DataValidationError(f"Failed to convert timestamps to UTC: {str(e)}")
        
        # Set timestamp as index
        df.set_index(timestamp_column, inplace=True)
        
        # Sort chronologically
        df.sort_index(inplace=True)
        
        # Detect and handle duplicates
        duplicates = df.index.duplicated(keep='first')
        if duplicates.any():
            dup_times = df.index[duplicates].tolist()
            raise DataValidationError(
                f"Duplicate timestamps detected: {len(dup_times)} duplicates. "
                f"First few: {dup_times[:5]}"
            )
        
        # Verify monotonic increasing
        if not df.index.is_monotonic_increasing:
            raise DataValidationError("Time index is not monotonically increasing after sorting")
        
        # Create metadata
        metadata = {
            'pair': pair,
            'start_date': df.index[0],
            'end_date': df.index[-1],
            'total_bars': len(df),
            'columns': list(df.columns),
            'has_spread': 'spread' in df.columns,
            'file_path': str(csv_path.absolute())
        }
        
        return df, metadata
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Perform basic data quality checks.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with quality metrics
            
        Examples:
            >>> quality = loader.validate_data_quality(df)
            >>> print(f"Missing bars: {quality['missing_bars_count']}")
        """
        quality = {
            'total_bars': len(df),
            'missing_values': df.isnull().sum().to_dict(),
            'date_range_days': (df.index[-1] - df.index[0]).days,
            'has_duplicates': df.index.duplicated().any(),
            'is_sorted': df.index.is_monotonic_increasing,
        }
        
        return quality
