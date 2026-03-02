"""
Pytest configuration and shared fixtures.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_fx_data():
    """Generate sample FX OHLC data for testing."""
    np.random.seed(42)
    
    dates = pd.date_range('2020-01-01', periods=100, freq='D', tz='UTC')
    
    # Generate price series
    returns = np.random.randn(100) * 0.01
    log_prices = np.log(1.1) + np.cumsum(returns)
    close = np.exp(log_prices)
    
    # Generate OHLC
    open_prices = close * (1 + np.random.randn(100) * 0.003)
    high = np.maximum(open_prices, close) * (1 + np.abs(np.random.randn(100)) * 0.005)
    low = np.minimum(open_prices, close) * (1 - np.abs(np.random.randn(100)) * 0.005)
    
    volume = np.random.uniform(100000, 500000, 100)
    spread = np.random.uniform(0.00008, 0.00012, 100)
    
    df = pd.DataFrame({
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'spread': spread
    }, index=dates)
    
    # Ensure OHLC logic
    df['high'] = df[['open', 'high', 'close', 'low']].max(axis=1)
    df['low'] = df[['open', 'high', 'close', 'low']].min(axis=1)
    
    return df


@pytest.fixture
def sample_csv_file(tmp_path, sample_fx_data):
    """Create a temporary CSV file with sample data."""
    csv_path = tmp_path / "sample_eurusd.csv"
    
    # Reset index to include timestamp as column
    df = sample_fx_data.copy()
    df.index.name = 'timestamp'
    df.reset_index().to_csv(csv_path, index=False)
    
    return csv_path


@pytest.fixture
def config_dict():
    """Sample configuration dictionary."""
    return {
        'data': {
            'raw_path': 'data/raw/',
            'timezone': 'UTC',
            'frequency': 'D'
        },
        'validation': {
            'spike_threshold': 5.0,
            'max_missing_pct': 5.0,
            'check_weekends': True
        },
        'costs': {
            'spread_bps': {
                'majors': 1.5,
                'minors': 3.0,
                'exotics': 10.0
            },
            'slippage_coefficient': 0.1,
            'market_impact_exponent': 0.5,
            'market_impact_coefficient': 0.05,
            'enable_swap_costs': False
        },
        'backtest': {
            'random_seed': 42,
            'execution_lag': 1,
            'initial_capital': 100000.0,
            'annualization_factor': 252
        },
        'regime': {
            'n_states': 3,
            'covariance_type': 'full',
            'max_iter': 100,
            'features': ['returns', 'volatility', 'volume_zscore']
        },
        'risk': {
            'max_drawdown_threshold': -0.15,
            'correlation_threshold': 0.7,
            'var_confidence': 0.95
        }
    }


@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test."""
    np.random.seed(42)
    yield
    # Cleanup after test
    np.random.seed(None)


@pytest.fixture
def mock_cost_model():
    """Simple mock cost model for testing."""
    class MockCostModel:
        def calculate_cost(self, price, size, side, timestamp, **kwargs):
            return abs(size) * 0.0001
        
        def total_cost(self, price, size, side, timestamp, **kwargs):
            cost = self.calculate_cost(price, size, side, timestamp)
            return {
                'total_cost': cost,
                'total_cost_bps': 1.0,
                'breakdown': {
                    'spread': cost,
                    'slippage': 0.0,
                    'market_impact': 0.0,
                    'swap': 0.0
                }
            }
    
    return MockCostModel()
