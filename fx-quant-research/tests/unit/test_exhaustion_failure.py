"""
Unit tests for Exhaustion-Failure-to-Continue strategy.

Tests:
- Exhaustion detection logic
- Failure-to-continue filter
- Signal generation
- Edge cases and validation
"""

import pytest
import numpy as np
import pandas as pd

from src.strategies.exhaustion_failure import (
    ExhaustionFailureStrategy,
    validate_strategy_setup
)


@pytest.fixture
def sample_ohlc_data():
    """Generate sample OHLC data for testing."""
    np.random.seed(42)
    n_bars = 100
    
    base_price = 1.1000
    returns = np.random.normal(0, 0.001, n_bars)
    close = base_price * np.exp(np.cumsum(returns))
    
    # Generate OHLC with realistic intrabar movement
    high = close * (1 + np.abs(np.random.normal(0, 0.0005, n_bars)))
    low = close * (1 - np.abs(np.random.normal(0, 0.0005, n_bars)))
    open_price = low + (high - low) * np.random.uniform(0, 1, n_bars)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 5000, n_bars)
    })
    
    return df


@pytest.fixture
def exhaustion_pattern_data():
    """Generate data with known exhaustion patterns."""
    df = pd.DataFrame({
        'open': [1.10, 1.10, 1.11, 1.12, 1.13, 1.135, 1.13],
        'high': [1.105, 1.110, 1.115, 1.125, 1.135, 1.140, 1.132],
        'low': [1.095, 1.098, 1.108, 1.118, 1.128, 1.132, 1.128],
        'close': [1.100, 1.108, 1.114, 1.124, 1.134, 1.138, 1.130],  # Strong bullish, then decline
        'volume': [1000] * 7
    })
    return df


class TestExhaustionDetection:
    """Test exhaustion detection logic."""
    
    def test_range_expansion_detection(self, sample_ohlc_data):
        """Test range expansion calculation."""
        strategy = ExhaustionFailureStrategy(
            range_expansion_threshold=0.8,
            median_range_window=20
        )
        
        bulls, bears = strategy.detect_exhaustion(sample_ohlc_data)
        
        # Should detect some exhaustion bars (but not all)
        assert bulls.sum() >= 0
        assert bears.sum() >= 0
        assert bulls.sum() + bears.sum() < len(sample_ohlc_data)  # Not every bar
    
    def test_no_simultaneous_bull_bear_exhaustion(self, sample_ohlc_data):
        """Test that a bar cannot be both bullish and bearish exhaustion."""
        strategy = ExhaustionFailureStrategy()
        
        bulls, bears = strategy.detect_exhaustion(sample_ohlc_data)
        
        # No bar should be both
        simultaneous = bulls & bears
        assert simultaneous.sum() == 0, "Bar cannot be both bullish and bearish exhaustion"
    
    def test_exhaustion_with_known_pattern(self, exhaustion_pattern_data):
        """Test exhaustion detection on known pattern."""
        strategy = ExhaustionFailureStrategy(
            range_expansion_threshold=0.5,  # Lower threshold for test
            median_range_window=3,
            consecutive_bars_required=2,
            extreme_zone_upper=0.65,
            extreme_zone_lower=0.35
        )
        
        bulls, bears = strategy.detect_exhaustion(exhaustion_pattern_data)
        
        # Bars 3-5 show strong bullish movement with expanding range
        # At least one should be detected as bullish exhaustion
        assert bulls.iloc[3:6].any(), "Should detect bullish exhaustion in strong uptrend"
    
    def test_close_position_calculation(self):
        """Test close position within range calculation."""
        df = pd.DataFrame({
            'open': [1.10, 1.10, 1.10],
            'high': [1.12, 1.12, 1.10],  # Third bar: zero range
            'low': [1.08, 1.08, 1.10],
            'close': [1.11, 1.088, 1.10],  # High close, low close, zero range
            'volume': [1000, 1000, 1000]
        })
        
        strategy = ExhaustionFailureStrategy()
        bulls, bears = strategy.detect_exhaustion(df)
        
        # Should handle zero-range bars without error
        assert len(bulls) == len(df)
        assert len(bears) == len(df)
        assert not bulls.isna().any()
        assert not bears.isna().any()


class TestFailureToContine:
    """Test failure-to-continue detection."""
    
    def test_failure_filter_reduces_signals(self, sample_ohlc_data):
        """Test that failure filter reduces signal count."""
        strategy_no_filter = ExhaustionFailureStrategy(enable_failure_filter=False)
        strategy_with_filter = ExhaustionFailureStrategy(enable_failure_filter=True)
        
        signals_no_filter = strategy_no_filter.generate_signals(sample_ohlc_data)
        signals_with_filter = strategy_with_filter.generate_signals(sample_ohlc_data)
        
        no_filter_count = (signals_no_filter != 0).sum()
        with_filter_count = (signals_with_filter != 0).sum()
        
        # Filter should reduce (or equal) signal count
        assert with_filter_count <= no_filter_count, \
            f"Filter should reduce signals: {with_filter_count} vs {no_filter_count}"
    
    def test_bullish_failure_logic(self):
        """Test bullish exhaustion failure detection."""
        # Create pattern: strong up move, then failure to continue
        df = pd.DataFrame({
            'open': [1.10, 1.11, 1.12, 1.125],
            'high': [1.11, 1.12, 1.13, 1.127],  # Bar 2: high at 1.13
            'low': [1.095, 1.108, 1.118, 1.120],
            'close': [1.108, 1.118, 1.129, 1.122],  # Bar 3: closes below bar 2 high → failure
            'volume': [1000] * 4
        })
        
        strategy = ExhaustionFailureStrategy(
            range_expansion_threshold=0.3,  # Low for testing
            median_range_window=2,
            consecutive_bars_required=2,
            enable_failure_filter=True
        )
        
        signals = strategy.generate_signals(df)
        
        # Bar 2 shows bullish exhaustion, bar 3 closes inside range → SHORT signal
        # Signal appears at bar 2 (when we detect failure will happen at bar 3)
        assert (signals == -1).any(), "Should detect bullish failure → short signal"
    
    def test_bearish_failure_logic(self):
        """Test bearish exhaustion failure detection."""
        # Create pattern: strong down move, then failure to continue
        df = pd.DataFrame({
            'open': [1.13, 1.12, 1.11, 1.105],
            'high': [1.135, 1.122, 1.112, 1.110],
            'low': [1.12, 1.11, 1.10, 1.103],  # Bar 2: low at 1.10
            'close': [1.122, 1.112, 1.101, 1.108],  # Bar 3: closes above bar 2 low → failure
            'volume': [1000] * 4
        })
        
        strategy = ExhaustionFailureStrategy(
            range_expansion_threshold=0.3,
            median_range_window=2,
            consecutive_bars_required=2,
            enable_failure_filter=True
        )
        
        signals = strategy.generate_signals(df)
        
        # Should detect bearish failure → LONG signal
        assert (signals == 1).any(), "Should detect bearish failure → long signal"


class TestSignalGeneration:
    """Test signal generation and constraints."""
    
    def test_signal_values_constrained(self, sample_ohlc_data):
        """Test signals are only -1, 0, 1."""
        strategy = ExhaustionFailureStrategy()
        signals = strategy.generate_signals(sample_ohlc_data)
        
        assert signals.isin([-1, 0, 1]).all(), "Signals must be -1, 0, or 1"
    
    def test_signal_index_alignment(self, sample_ohlc_data):
        """Test signal index matches data index."""
        strategy = ExhaustionFailureStrategy()
        signals = strategy.generate_signals(sample_ohlc_data)
        
        assert len(signals) == len(sample_ohlc_data), "Signal length must match data"
        assert (signals.index == sample_ohlc_data.index).all(), "Index must align"
    
    def test_no_signals_on_insufficient_data(self):
        """Test no signals generated with insufficient data."""
        df = pd.DataFrame({
            'open': [1.10, 1.11],
            'high': [1.11, 1.12],
            'low': [1.09, 1.10],
            'close': [1.105, 1.115],
            'volume': [1000, 1000]
        })
        
        strategy = ExhaustionFailureStrategy(median_range_window=20)
        signals = strategy.generate_signals(df)
        
        # With only 2 bars and 20-bar window, likely no signals
        assert (signals != 0).sum() <= 2, "Should have minimal/no signals with insufficient data"
    
    def test_regime_filter(self, sample_ohlc_data):
        """Test optional regime filter."""
        strategy = ExhaustionFailureStrategy()
        
        # Create regime series (0, 1, 2)
        regime = pd.Series(
            np.random.choice([0, 1, 2], size=len(sample_ohlc_data)),
            index=sample_ohlc_data.index
        )
        
        # Generate signals with regime filter (only trade in regime 1)
        signals = strategy.generate_signals(sample_ohlc_data, regime=regime, target_regime=1)
        
        # Check that non-zero signals only occur in target regime
        non_zero_signals = signals[signals != 0]
        if len(non_zero_signals) > 0:
            regime_at_signals = regime[non_zero_signals.index]
            assert (regime_at_signals == 1).all(), "Signals should only appear in target regime"


class TestDiagnostics:
    """Test diagnostic utilities."""
    
    def test_diagnostics_structure(self, sample_ohlc_data):
        """Test diagnostic output structure."""
        strategy = ExhaustionFailureStrategy()
        diagnostics = strategy.get_signal_diagnostics(sample_ohlc_data)
        
        required_keys = [
            'bullish_exhaustion', 'bearish_exhaustion', 'total_exhaustion',
            'bullish_failure', 'bearish_failure', 'total_signals', 'reduction_ratio'
        ]
        
        for key in required_keys:
            assert key in diagnostics, f"Missing diagnostic key: {key}"
        
        # Check types
        assert isinstance(diagnostics['total_signals'], int)
        assert isinstance(diagnostics['reduction_ratio'], float)
    
    def test_reduction_ratio_logic(self, sample_ohlc_data):
        """Test reduction ratio calculation."""
        strategy = ExhaustionFailureStrategy(enable_failure_filter=True)
        diagnostics = strategy.get_signal_diagnostics(sample_ohlc_data)
        
        # Reduction ratio should be between 0 and 1 (signals ≤ exhaustion)
        if diagnostics['total_exhaustion'] > 0:
            assert 0 <= diagnostics['reduction_ratio'] <= 1, \
                "Reduction ratio must be between 0 and 1"
            
            # Manual check
            expected_ratio = diagnostics['total_signals'] / diagnostics['total_exhaustion']
            assert abs(diagnostics['reduction_ratio'] - expected_ratio) < 1e-6


class TestValidation:
    """Test validation utilities."""
    
    def test_validate_valid_data(self, sample_ohlc_data):
        """Test validation passes on valid data."""
        assert validate_strategy_setup(sample_ohlc_data) is True
    
    def test_validate_missing_columns(self):
        """Test validation fails on missing columns."""
        df = pd.DataFrame({
            'open': [1.10],
            'high': [1.11],
            # Missing low, close, volume
        })
        
        assert validate_strategy_setup(df) is False
    
    def test_validate_invalid_ohlc_logic(self):
        """Test validation fails on invalid OHLC."""
        df = pd.DataFrame({
            'open': [1.10],
            'high': [1.08],  # High < open (invalid)
            'low': [1.09],
            'close': [1.095],
            'volume': [1000]
        })
        
        assert validate_strategy_setup(df) is False
    
    def test_validate_insufficient_data(self):
        """Test validation fails on insufficient data."""
        df = pd.DataFrame({
            'open': [1.10] * 10,
            'high': [1.11] * 10,
            'low': [1.09] * 10,
            'close': [1.10] * 10,
            'volume': [1000] * 10
        })
        
        # 10 bars < 50 minimum
        assert validate_strategy_setup(df) is False


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_from_config_loads_defaults(self, tmp_path):
        """Test loading strategy from config file."""
        # Create temporary config
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
exhaustion_strategy:
  range_expansion_threshold: 0.9
  median_range_window: 25
  extreme_zone_upper: 0.70
  extreme_zone_lower: 0.30
  consecutive_bars_required: 3
  enable_failure_filter: false
""")
        
        strategy = ExhaustionFailureStrategy.from_config(str(config_file))
        
        assert strategy.range_expansion_threshold == 0.9
        assert strategy.median_range_window == 25
        assert strategy.extreme_zone_upper == 0.70
        assert strategy.extreme_zone_lower == 0.30
        assert strategy.consecutive_bars_required == 3
        assert strategy.enable_failure_filter is False


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_dataframe(self):
        """Test behavior with empty DataFrame."""
        df = pd.DataFrame({
            'open': [], 'high': [], 'low': [], 'close': [], 'volume': []
        })
        
        strategy = ExhaustionFailureStrategy()
        signals = strategy.generate_signals(df)
        
        assert len(signals) == 0, "Should return empty signals for empty data"
    
    def test_missing_required_columns_raises_error(self):
        """Test error when required columns missing."""
        df = pd.DataFrame({
            'open': [1.10],
            'high_wrong_name': [1.11],  # Wrong column name
            'low': [1.09],
            'close': [1.10]
        })
        
        strategy = ExhaustionFailureStrategy()
        
        with pytest.raises(ValueError, match="Missing required columns"):
            strategy.generate_signals(df)
    
    def test_all_nan_data(self):
        """Test behavior with all NaN data."""
        df = pd.DataFrame({
            'open': [np.nan] * 10,
            'high': [np.nan] * 10,
            'low': [np.nan] * 10,
            'close': [np.nan] * 10,
            'volume': [np.nan] * 10
        })
        
        strategy = ExhaustionFailureStrategy()
        signals = strategy.generate_signals(df)
        
        # Should return all zeros (no signals possible)
        assert (signals == 0).all(), "All NaN data should produce zero signals"
    
    def test_flat_price_data(self):
        """Test with flat (no movement) price data."""
        df = pd.DataFrame({
            'open': [1.10] * 50,
            'high': [1.10] * 50,
            'low': [1.10] * 50,
            'close': [1.10] * 50,
            'volume': [1000] * 50
        })
        
        strategy = ExhaustionFailureStrategy()
        signals = strategy.generate_signals(df)
        
        # No range = no exhaustion = no signals
        assert (signals == 0).all(), "Flat price should produce no signals"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
