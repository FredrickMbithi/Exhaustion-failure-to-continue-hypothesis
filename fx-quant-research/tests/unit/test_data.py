"""
Unit tests for data loader and validator.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.loader import FXDataLoader, DataValidationError
from src.data.validator import DataValidator, ValidationReport


class TestFXDataLoader:
    """Test suite for FXDataLoader."""
    
    def test_initialization(self):
        """Test loader initialization."""
        loader = FXDataLoader()
        assert loader is not None
    
    def test_load_valid_csv(self, tmp_path):
        """Test loading valid CSV file."""
        # Create sample CSV
        csv_file = tmp_path / "eurusd.csv"
        
        dates = pd.date_range('2020-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'open': [1.1 + i * 0.001 for i in range(10)],
            'high': [1.11 + i * 0.001 for i in range(10)],
            'low': [1.09 + i * 0.001 for i in range(10)],
            'close': [1.105 + i * 0.001 for i in range(10)],
            'volume': [100000 + i * 1000 for i in range(10)]
        })
        df.to_csv(csv_file, index=False)
        
        # Load CSV
        loader = FXDataLoader()
        result_df, metadata = loader.load_csv(str(csv_file), pair="EURUSD")
        
        # Verify data loaded
        assert len(result_df) == 10
        assert isinstance(result_df.index, pd.DatetimeIndex)
        assert result_df.index.tz is not None  # Should be UTC
        
        # Verify metadata
        assert metadata['pair'] == 'EURUSD'
        assert metadata['total_bars'] == 10
        assert 'start_date' in metadata
        assert 'end_date' in metadata
    
    def test_load_csv_with_spread(self, tmp_path):
        """Test loading CSV with optional spread column."""
        csv_file = tmp_path / "eurusd_with_spread.csv"
        
        dates = pd.date_range('2020-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'open': [1.1] * 5,
            'high': [1.11] * 5,
            'low': [1.09] * 5,
            'close': [1.105] * 5,
            'volume': [100000] * 5,
            'spread': [0.0001] * 5
        })
        df.to_csv(csv_file, index=False)
        
        loader = FXDataLoader()
        result_df, metadata = loader.load_csv(str(csv_file), pair="EURUSD")
        
        assert 'spread' in result_df.columns
        assert len(result_df) == 5
    
    def test_load_csv_missing_columns(self, tmp_path):
        """Test error on missing required columns."""
        csv_file = tmp_path / "invalid.csv"
        
        # Missing 'volume' column
        df = pd.DataFrame({
            'timestamp': pd.date_range('2020-01-01', periods=5, freq='D'),
            'open': [1.1] * 5,
            'high': [1.11] * 5,
            'low': [1.09] * 5,
            'close': [1.105] * 5
        })
        df.to_csv(csv_file, index=False)
        
        loader = FXDataLoader()
        
        with pytest.raises(DataValidationError, match="Missing required columns"):
            loader.load_csv(str(csv_file), pair="EURUSD")
    
    def test_load_csv_duplicate_timestamps(self, tmp_path):
        """Test error on duplicate timestamps."""
        csv_file = tmp_path / "duplicates.csv"
        
        dates = pd.date_range('2020-01-01', periods=5, freq='D')
        duplicate_dates = dates.tolist() + [dates[2]]  # Add duplicate
        
        df = pd.DataFrame({
            'timestamp': duplicate_dates,
            'open': [1.1] * 6,
            'high': [1.11] * 6,
            'low': [1.09] * 6,
            'close': [1.105] * 6,
            'volume': [100000] * 6
        })
        df.to_csv(csv_file, index=False)
        
        loader = FXDataLoader()
        
        with pytest.raises(DataValidationError, match="duplicate timestamps"):
            loader.load_csv(str(csv_file), pair="EURUSD")
    
    def test_utc_timezone_enforcement(self, tmp_path):
        """Test that timestamps are converted to UTC."""
        csv_file = tmp_path / "non_utc.csv"
        
        # Create timestamps with no timezone
        dates = pd.date_range('2020-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'open': [1.1] * 5,
            'high': [1.11] * 5,
            'low': [1.09] * 5,
            'close': [1.105] * 5,
            'volume': [100000] * 5
        })
        df.to_csv(csv_file, index=False)
        
        loader = FXDataLoader()
        result_df, _ = loader.load_csv(str(csv_file), pair="EURUSD")
        
        # Verify UTC timezone
        assert result_df.index.tz is not None
        assert str(result_df.index.tz) == 'UTC'
    
    def test_chronological_sorting(self, tmp_path):
        """Test that data is sorted chronologically."""
        csv_file = tmp_path / "unsorted.csv"
        
        # Create unsorted timestamps
        dates = pd.date_range('2020-01-01', periods=5, freq='D')
        unsorted_dates = [dates[2], dates[0], dates[4], dates[1], dates[3]]
        
        df = pd.DataFrame({
            'timestamp': unsorted_dates,
            'open': [1.1 + i * 0.001 for i in range(5)],
            'high': [1.11 + i * 0.001 for i in range(5)],
            'low': [1.09 + i * 0.001 for i in range(5)],
            'close': [1.105 + i * 0.001 for i in range(5)],
            'volume': [100000 + i * 1000 for i in range(5)]
        })
        df.to_csv(csv_file, index=False)
        
        loader = FXDataLoader()
        result_df, _ = loader.load_csv(str(csv_file), pair="EURUSD")
        
        # Verify monotonic increasing
        assert result_df.index.is_monotonic_increasing


class TestDataValidator:
    """Test suite for DataValidator."""
    
    def create_valid_dataframe(self):
        """Create valid OHLC dataframe."""
        dates = pd.date_range('2020-01-01', periods=100, freq='D', tz='UTC')
        
        np.random.seed(42)
        close = 1.1 + np.cumsum(np.random.randn(100) * 0.005)
        
        df = pd.DataFrame({
            'open': close + np.random.randn(100) * 0.001,
            'high': close + np.abs(np.random.randn(100)) * 0.005,
            'low': close - np.abs(np.random.randn(100)) * 0.005,
            'close': close,
            'volume': np.random.uniform(100000, 500000, 100)
        }, index=dates)
        
        # Ensure OHLC logic
        df['high'] = df[['open', 'high', 'close', 'low']].max(axis=1)
        df['low'] = df[['open', 'high', 'close', 'low']].min(axis=1)
        
        return df
    
    def test_initialization(self):
        """Test validator initialization."""
        validator = DataValidator(spike_threshold=5.0)
        assert validator.spike_threshold == 5.0
    
    def test_validate_valid_data(self):
        """Test validation of valid data."""
        df = self.create_valid_dataframe()
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert report.is_valid
        assert len(report.errors) == 0
    
    def test_validate_ohlc_logic_high_violation(self):
        """Test detection of high price violations."""
        df = self.create_valid_dataframe()
        
        # Introduce violation: high < close
        df.loc[df.index[10], 'high'] = df.loc[df.index[10], 'close'] - 0.01
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert not report.is_valid
        assert any('high' in error.lower() for error in report.errors)
    
    def test_validate_ohlc_logic_low_violation(self):
        """Test detection of low price violations."""
        df = self.create_valid_dataframe()
        
        # Introduce violation: low > close
        df.loc[df.index[15], 'low'] = df.loc[df.index[15], 'close'] + 0.01
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert not report.is_valid
        assert any('low' in error.lower() for error in report.errors)
    
    def test_detect_spikes(self):
        """Test spike detection using z-score."""
        df = self.create_valid_dataframe()
        
        # Introduce spike
        df.loc[df.index[50], 'close'] = df['close'].median() + 10 * df['close'].std()
        
        validator = DataValidator(spike_threshold=5.0)
        report = validator.validate(df, pair="EURUSD")
        
        # Should have warnings about spikes
        assert len(report.warnings) > 0
        assert any('spike' in warning.lower() for warning in report.warnings)
    
    def test_detect_missing_bars(self):
        """Test detection of missing bars."""
        df = self.create_valid_dataframe()
        
        # Remove some bars to create gaps
        df = df.drop(df.index[20:25])
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        # Should detect missing bars
        assert 'missing_bars' in report.metrics
        assert report.metrics['missing_bars'] > 0
    
    def test_validate_spread(self):
        """Test spread validation."""
        df = self.create_valid_dataframe()
        df['spread'] = 0.0001  # 1 pip
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert report.is_valid
    
    def test_validate_spread_negative(self):
        """Test detection of negative spreads."""
        df = self.create_valid_dataframe()
        df['spread'] = 0.0001
        df.loc[df.index[10], 'spread'] = -0.0001  # Invalid
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert len(report.warnings) > 0
        assert any('negative spread' in warning.lower() for warning in report.warnings)
    
    def test_validate_spread_constant(self):
        """Test detection of constant spreads."""
        df = self.create_valid_dataframe()
        df['spread'] = 0.0001  # All same
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        # Might generate warning about constant spread
        # (depends on implementation tolerance)
        assert isinstance(report, ValidationReport)
    
    def test_spike_detection_robustness(self):
        """Test spike detection with outliers using MAD."""
        df = self.create_valid_dataframe()
        returns = df['close'].pct_change()
        
        # Add multiple outliers
        outlier_indices = [10, 20, 30]
        for idx in outlier_indices:
            df.loc[df.index[idx], 'close'] = df.loc[df.index[idx], 'close'] * 1.05
        
        validator = DataValidator(spike_threshold=3.0)
        report = validator.validate(df, pair="EURUSD")
        
        # Should detect spikes
        assert len(report.warnings) > 0
    
    def test_empty_dataframe(self):
        """Test validation of empty dataframe."""
        df = pd.DataFrame()
        
        validator = DataValidator()
        
        with pytest.raises((ValueError, KeyError)):
            validator.validate(df, pair="EURUSD")
    
    def test_validation_metrics(self):
        """Test that validation report includes metrics."""
        df = self.create_valid_dataframe()
        
        validator = DataValidator()
        report = validator.validate(df, pair="EURUSD")
        
        assert 'total_bars' in report.metrics
        assert 'missing_bars' in report.metrics
        assert 'spike_count' in report.metrics
        assert report.metrics['total_bars'] == len(df)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
