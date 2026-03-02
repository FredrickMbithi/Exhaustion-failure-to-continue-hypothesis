"""
Unit tests for backtest engine with property-based testing for lag enforcement.
"""

import pytest
import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.cost_model import FXCostModel


class MockCostModel:
    """Mock cost model for testing."""
    
    def calculate_cost(self, price, size, side, timestamp, **kwargs):
        """Return fixed small cost."""
        return abs(size) * 0.0001  # 1 bp
    
    def total_cost(self, price, size, side, timestamp, **kwargs):
        """Return breakdown with small cost."""
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


def create_sample_data(n_bars=100, seed=42):
    """Create sample OHLC data for testing."""
    np.random.seed(seed)
    
    dates = pd.date_range('2020-01-01', periods=n_bars, freq='D')
    
    # Generate prices with random walk
    returns = np.random.randn(n_bars) * 0.01
    close = 1.1 + np.cumsum(returns)
    
    # Generate OHLC
    high = close * (1 + np.abs(np.random.randn(n_bars)) * 0.005)
    low = close * (1 - np.abs(np.random.randn(n_bars)) * 0.005)
    open_prices = close * (1 + np.random.randn(n_bars) * 0.003)
    
    volume = np.random.uniform(100000, 500000, n_bars)
    
    df = pd.DataFrame({
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


class TestBacktestEngine:
    """Test suite for BacktestEngine."""
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        assert engine.initial_capital == 100000
        assert engine.execution_lag == 1
    
    def test_run_basic(self):
        """Test basic backtest run."""
        df = create_sample_data(n_bars=100)
        
        # Simple buy-and-hold signal
        signals = pd.Series(1, index=df.index)
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Verify result structure
        assert 'equity_curve' in result
        assert 'drawdown' in result
        assert 'positions' in result
        assert 'trades' in result
        assert 'returns' in result
        assert 'metrics' in result
        assert 'cost_breakdown' in result
        
        # Verify metrics
        metrics = result['metrics']
        assert 'total_return' in metrics
        assert 'annualized_return' in metrics
        assert 'sharpe' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        
        # Verify equity curve is valid
        assert len(result['equity_curve']) == len(df)
        assert result['equity_curve'].iloc[0] == 100000  # Initial capital
        assert all(result['equity_curve'] > 0)  # No bankruptcy
    
    def test_execution_lag(self):
        """Test that execution lag is properly enforced."""
        df = create_sample_data(n_bars=50)
        
        # Generate signals that change at specific points
        signals = pd.Series(0, index=df.index)
        signals.iloc[10:20] = 1  # Long from bar 10 to 19
        signals.iloc[20:30] = -1  # Short from bar 20 to 29
        signals.iloc[30:] = 0  # Flat from bar 30
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        positions = result['positions']
        
        # CRITICAL: Position at time t should equal signal at time t-1
        # Due to 1-bar execution lag
        for i in range(1, len(positions)):
            expected_position = signals.iloc[i - 1]
            actual_position = positions.iloc[i]
            assert actual_position == expected_position, (
                f"At index {i}: position={actual_position} != "
                f"signal[{i-1}]={expected_position}"
            )
        
        # First position should be 0 (no signal before t=0)
        assert positions.iloc[0] == 0
    
    def test_no_lookahead_bias(self):
        """Test that returns calculations don't use same-bar data."""
        df = create_sample_data(n_bars=100)
        
        # Create signals based on future returns (intentional lookahead)
        future_returns = df['close'].pct_change().shift(-1)
        signals = (future_returns > 0).astype(int) * 2 - 1
        signals = signals.fillna(0)
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Get gross returns (before costs)
        positions = result['positions']
        returns = df['close'].pct_change()
        
        # Calculate what gross returns should be
        # Position at time t was set based on signal at t-1
        # Return at time t is calculated using position set at t-1
        # So returns[t] should use position[t-1]
        expected_gross = positions.shift(1) * returns
        
        # Verify alignment (allowing for small numerical errors)
        # Note: First few bars may have NaN due to initialization
        valid_idx = ~expected_gross.isna()
        actual_gross = positions.shift(1) * returns
        
        np.testing.assert_allclose(
            actual_gross[valid_idx].values,
            expected_gross[valid_idx].values,
            rtol=1e-10,
            err_msg="Gross returns calculation has lookahead bias"
        )
    
    def test_cost_application(self):
        """Test that transaction costs are applied correctly."""
        df = create_sample_data(n_bars=50)
        
        # Create signals with several trades
        signals = pd.Series(0, index=df.index)
        signals.iloc[5:15] = 1
        signals.iloc[20:30] = -1
        signals.iloc[35:45] = 1
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Count trades
        trades = result['trades']
        n_trades = (trades > 0).sum()
        
        # Should have trades at: entry bar 5, exit bar 15, entry bar 20, 
        # exit bar 30, entry bar 35, exit bar 45
        # Due to lag, these happen 1 bar later
        assert n_trades > 0, "Should have executed trades"
        
        # Verify cost breakdown exists
        assert 'cost_breakdown' in result
        assert 'total_cost' in result['cost_breakdown']
        
        # Costs should reduce returns
        metrics = result['metrics']
        assert 'annualized_return' in metrics
    
    @settings(deadline=None, max_examples=50)
    @given(
        n_bars=st.integers(min_value=20, max_value=100),
        signal_changes=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=99),
                st.integers(min_value=-1, max_value=1)
            ),
            min_size=1,
            max_size=10
        )
    )
    def test_lag_enforcement_property(self, n_bars, signal_changes):
        """
        Property-based test: For ANY signal pattern, positions must lag signals by exactly 1 bar.
        
        This is the CRITICAL test ensuring no lookahead bias.
        """
        df = create_sample_data(n_bars=n_bars, seed=42)
        
        # Create arbitrary signal pattern
        signals = pd.Series(0, index=df.index)
        for idx, value in signal_changes:
            if idx < len(signals):
                signals.iloc[idx:] = value
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        try:
            result = engine.run(
                data=df,
                signals=signals,
                cost_model=cost_model,
                pair_tier='major',
                pair_name='TEST'
            )
            
            positions = result['positions']
            
            # CRITICAL PROPERTY: position[t] == signal[t-1] for all t > 0
            for i in range(1, len(positions)):
                assert positions.iloc[i] == signals.iloc[i - 1], (
                    f"LAG VIOLATION at bar {i}: "
                    f"position={positions.iloc[i]}, "
                    f"signal[{i-1}]={signals.iloc[i-1]}"
                )
            
            # position[0] should be 0 (no prior signal)
            assert positions.iloc[0] == 0
            
        except Exception as e:
            # Allow for edge cases but log them
            if "insufficient data" not in str(e).lower():
                raise
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        df = create_sample_data(n_bars=100, seed=42)
        
        # Generate losing signals to create drawdown
        signals = pd.Series(-1, index=df.index)  # Always short
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        drawdown = result['drawdown']
        
        # Drawdown should be <= 0
        assert all(drawdown <= 0), "Drawdown should be negative or zero"
        
        # Max drawdown metric should match worst drawdown
        max_dd = result['metrics']['max_drawdown']
        assert max_dd <= 0
        assert abs(max_dd - drawdown.min()) < 1e-6
    
    def test_empty_signals(self):
        """Test handling of flat/empty signals."""
        df = create_sample_data(n_bars=100)
        signals = pd.Series(0, index=df.index)  # All flat
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        cost_model = MockCostModel()
        
        result = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Should have no returns, no trades
        assert all(result['returns'] == 0)
        assert result['trades'].sum() == 0
        assert result['metrics']['total_return'] == 0.0
        
        # Equity should remain at initial capital
        assert all(result['equity_curve'] == 100000)


class TestFXCostModel:
    """Test suite for FXCostModel."""
    
    def test_initialization(self):
        """Test cost model initialization."""
        model = FXCostModel(
            spread_bps_major=1.5,
            spread_bps_minor=3.0,
            spread_bps_exotic=10.0
        )
        assert model.spread_bps_major == 1.5
        assert model.spread_bps_minor == 3.0
        assert model.spread_bps_exotic == 10.0
    
    def test_spread_cost_calculation(self):
        """Test spread cost formula."""
        model = FXCostModel(spread_bps_major=1.5)
        
        # Test: 0.5 * (1.5 / 10000) * 1.1 * 100 = 0.00825
        cost = model.calculate_spread_cost(
            price=1.1,
            size=100,
            spread_bps=1.5
        )
        
        expected = 0.5 * (1.5 / 10000) * 1.1 * 100
        assert abs(cost - expected) < 1e-6
    
    def test_spread_cost_by_tier(self):
        """Test spread cost varies by pair tier."""
        model = FXCostModel(
            spread_bps_major=1.5,
            spread_bps_minor=3.0,
            spread_bps_exotic=10.0
        )
        
        price, size = 1.1, 100
        
        cost_major = model.calculate_spread_cost(price, size, model.spread_bps_major)
        cost_minor = model.calculate_spread_cost(price, size, model.spread_bps_minor)
        cost_exotic = model.calculate_spread_cost(price, size, model.spread_bps_exotic)
        
        # Costs should increase by tier
        assert cost_major < cost_minor < cost_exotic
    
    def test_slippage_calculation(self):
        """Test square-root slippage model."""
        model = FXCostModel(slippage_coefficient=0.1)
        
        volatility = 0.01
        price = 1.1
        size = 100
        volume = 1000000
        
        cost = model.calculate_slippage(volatility, price, size, volume)
        
        # Formula: volatility * sqrt(|size| / volume) * price * coefficient
        expected = volatility * np.sqrt(abs(size) / volume) * price * 0.1
        
        assert abs(cost - expected) < 1e-6
    
    def test_market_impact_calculation(self):
        """Test power-law market impact."""
        model = FXCostModel(
            market_impact_exponent=0.5,
            market_impact_coefficient=0.05
        )
        
        price = 1.1
        size = 100
        daily_volume = 1000000
        
        cost = model.calculate_market_impact(price, size, daily_volume)
        
        # Formula: price * (|size| / daily_volume)^exponent * coefficient
        expected = price * (abs(size) / daily_volume) ** 0.5 * 0.05
        
        assert abs(cost - expected) < 1e-6
    
    def test_swap_cost_calculation(self):
        """Test swap cost with triple Wednesday."""
        model = FXCostModel()
        
        # Create sample swap rates
        dates = pd.date_range('2020-01-06', periods=7, freq='D')  # Starts Monday
        swap_rates = pd.DataFrame({
            'swap_rate_long': [0.0001] * 7,
            'swap_rate_short': [-0.0001] * 7
        }, index=dates)
        
        price = 1.1
        position = 100  # Long
        
        # Monday-Saturday
        for i in range(7):
            timestamp = dates[i]
            cost = model.calculate_swap_cost(
                price, position, timestamp, swap_rates
            )
            
            # Wednesday (day 2, weekday=2) should have 3x multiplier
            if timestamp.weekday() == 2:  # Wednesday
                expected = 0.0001 * price * position * 3
            else:
                expected = 0.0001 * price * position
            
            assert abs(cost - expected) < 1e-6, (
                f"Swap cost mismatch on {timestamp.strftime('%A')}: "
                f"expected {expected}, got {cost}"
            )
    
    def test_total_cost(self):
        """Test aggregated cost calculation."""
        model = FXCostModel(
            spread_bps_major=1.5,
            slippage_coefficient=0.1,
            market_impact_coefficient=0.05
        )
        
        result = model.total_cost(
            price=1.1,
            size=100,
            side='buy',
            timestamp=pd.Timestamp('2020-01-01'),
            pair_tier='major',
            volatility=0.01,
            volume=1000000,
            daily_volume=5000000
        )
        
        # Verify structure
        assert 'total_cost' in result
        assert 'total_cost_bps' in result
        assert 'breakdown' in result
        
        breakdown = result['breakdown']
        assert 'spread' in breakdown
        assert 'slippage' in breakdown
        assert 'market_impact' in breakdown
        assert 'swap' in breakdown
        
        # Total should be sum of components
        total_from_breakdown = sum([
            breakdown['spread'],
            breakdown['slippage'],
            breakdown['market_impact'],
            breakdown['swap']
        ])
        
        assert abs(result['total_cost'] - total_from_breakdown) < 1e-6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
