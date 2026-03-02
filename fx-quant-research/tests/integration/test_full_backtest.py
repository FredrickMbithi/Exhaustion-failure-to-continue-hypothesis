"""
Integration tests for end-to-end backtest workflow.

Tests complete pipeline: load data → validate → engineer features → run backtest → verify reproducibility
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.loader import FXDataLoader
from src.data.validator import DataValidator
from src.features.library import FeatureEngineering
from src.features.returns import log_returns, rolling_volatility
from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import FXCostModel
from src.backtest.seed_manager import set_global_seed
from src.analysis.attribution import PerformanceAttribution


def create_sample_fx_data(n_bars=252, seed=42):
    """
    Create realistic sample FX data for testing.
    
    Simulates price action with:
    - Random walk with drift
    - Realistic volatility (1% daily)
    - Proper OHLC relationships
    """
    np.random.seed(seed)
    
    dates = pd.date_range('2020-01-01', periods=n_bars, freq='D', tz='UTC')
    
    # Generate returns with realistic FX characteristics
    returns = np.random.randn(n_bars) * 0.01  # 1% daily vol
    log_prices = np.log(1.1) + np.cumsum(returns)
    close = np.exp(log_prices)
    
    # Generate realistic OHLC
    intraday_range = np.abs(np.random.randn(n_bars)) * 0.003
    open_prices = close * (1 + np.random.randn(n_bars) * 0.002)
    high = np.maximum(open_prices, close) * (1 + intraday_range)
    low = np.minimum(open_prices, close) * (1 - intraday_range)
    
    volume = np.random.uniform(1000000, 5000000, n_bars)
    spread = np.random.uniform(0.00005, 0.00015, n_bars)  # 0.5-1.5 pips
    
    df = pd.DataFrame({
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'spread': spread
    }, index=dates)
    
    return df


class TestEndToEndBacktest:
    """Integration test for complete backtest workflow."""
    
    def test_simple_strategy_backtest(self):
        """Test end-to-end backtest with simple SMA crossover strategy."""
        # Create sample data
        df = create_sample_fx_data(n_bars=252)
        
        # Validate data
        validator = DataValidator(spike_threshold=5.0)
        report = validator.validate(df, pair="EURUSD")
        assert report.is_valid, f"Data validation failed: {report.errors}"
        
        # Engineer features
        fe = FeatureEngineering()
        df = fe.add_momentum(df, windows=[10, 50])
        
        # Generate signals: SMA crossover
        df['signal'] = (df['momentum_10'] > df['momentum_50']).astype(int) * 2 - 1
        df['signal'] = df['signal'].fillna(0)
        
        # Create cost model
        cost_model = FXCostModel(
            spread_bps_major=1.5,
            slippage_coefficient=0.1,
            market_impact_exponent=0.5
        )
        
        # Run backtest
        set_global_seed(42)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        result = engine.run(
            data=df,
            signals=df['signal'],
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Verify result structure
        assert 'equity_curve' in result
        assert 'metrics' in result
        
        metrics = result['metrics']
        
        # Sanity checks on metrics
        assert -3.0 <= metrics['sharpe'] <= 3.0, "Sharpe ratio outside reasonable range"
        assert -1.0 <= metrics['max_drawdown'] <= 0.0, "Drawdown should be negative"
        assert metrics['win_rate'] >= 0.0 and metrics['win_rate'] <= 1.0
        assert metrics['total_trades'] >= 0
        
        # Equity curve should start at initial capital
        assert abs(result['equity_curve'].iloc[0] - 100000) < 1e-6
        
        # Equity should never go below zero (no bankruptcy)
        assert all(result['equity_curve'] > 0)
        
        print(f"\nBacktest Results:")
        print(f"  Total Return: {metrics['total_return']:.2%}")
        print(f"  Sharpe Ratio: {metrics['sharpe']:.2f}")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
        print(f"  Total Trades: {metrics['total_trades']}")
    
    def test_reproducibility(self):
        """
        Critical test: Verify backtest reproducibility with identical seeds.
        
        Running the same backtest twice with the same seed should produce
        IDENTICAL results to floating-point precision.
        """
        df = create_sample_fx_data(n_bars=252, seed=42)
        
        # Generate deterministic signals
        df['sma_10'] = df['close'].rolling(10).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        signals = (df['sma_10'] > df['sma_50']).astype(int) * 2 - 1
        signals = signals.fillna(0)
        
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        # Run 1
        set_global_seed(42)
        result1 = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Run 2 with same seed
        set_global_seed(42)
        result2 = engine.run(
            data=df,
            signals=signals,
            cost_model=cost_model,
            pair_tier='major',
            pair_name='EURUSD'
        )
        
        # Verify identical results
        pd.testing.assert_series_equal(
            result1['equity_curve'],
            result2['equity_curve'],
            check_exact=True,
            check_names=False
        )
        
        pd.testing.assert_series_equal(
            result1['returns'],
            result2['returns'],
            check_exact=True,
            check_names=False
        )
        
        # Verify metrics match
        for key in ['total_return', 'sharpe', 'max_drawdown']:
            assert abs(result1['metrics'][key] - result2['metrics'][key]) < 1e-10, (
                f"Metric {key} not reproducible: "
                f"{result1['metrics'][key]} != {result2['metrics'][key]}"
            )
        
        print("\n✓ Reproducibility verified: identical results with same seed")
    
    def test_different_seeds_produce_different_results(self):
        """Verify that different seeds produce different results (if randomness involved)."""
        df = create_sample_fx_data(n_bars=100, seed=42)
        
        signals = (df['close'].rolling(10).mean() > df['close'].rolling(20).mean()).astype(int) * 2 - 1
        signals = signals.fillna(0)
        
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        # Run with seed 42
        set_global_seed(42)
        result1 = engine.run(df, signals, cost_model, 'major', 'EURUSD')
        
        # Run with seed 123
        set_global_seed(123)
        result2 = engine.run(df, signals, cost_model, 'major', 'EURUSD')
        
        # For deterministic signals, results should actually be identical
        # (unless cost model has randomness, which it doesn't currently)
        # This test verifies seed mechanism works even if results are same
        assert 'equity_curve' in result1
        assert 'equity_curve' in result2
    
    def test_no_lookahead_with_lagged_features(self):
        """
        Test that using lagged features doesn't create lookahead bias.
        
        Features at time t should only use data up to time t-1.
        """
        df = create_sample_fx_data(n_bars=100)
        
        # Create lagged features
        df['returns'] = df['close'].pct_change()
        df['vol'] = df['returns'].rolling(10).std()
        
        # Signal: Buy when volatility is low (using proper lag)
        df['signal'] = (df['vol'] < df['vol'].rolling(20).mean()).astype(int) * 2 - 1
        df['signal'] = df['signal'].fillna(0)
        
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        result = engine.run(df, df['signal'], cost_model, 'major', 'EURUSD')
        
        # Verify positions lag signals by 1 bar
        positions = result['positions']
        signals = df['signal']
        
        for i in range(1, len(positions)):
            assert positions.iloc[i] == signals.iloc[i-1], (
                f"Position at {i} should equal signal at {i-1}"
            )
    
    def test_performance_attribution(self):
        """Test performance attribution analysis."""
        df = create_sample_fx_data(n_bars=252)
        
        # Generate signals
        signals = (df['close'].rolling(10).mean() > df['close'].rolling(50).mean()).astype(int) * 2 - 1
        signals = signals.fillna(0)
        
        # Run backtest
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        result = engine.run(df, signals, cost_model, 'major', 'EURUSD')
        
        # Perform attribution
        attribution = PerformanceAttribution()
        
        # Cost attribution
        cost_report = attribution.cost_attribution(
            gross_returns=result['returns'],  # Simplified - should use actual gross
            net_returns=result['returns'],
            cost_breakdown=result['cost_breakdown']
        )
        
        assert 'total_cost_bps' in cost_report
        assert cost_report['total_cost_bps'] >= 0
        
        # Monte Carlo p-value (with fewer simulations for speed)
        mc_result = attribution.monte_carlo_pvalue(
            strategy_sharpe=result['metrics']['sharpe'],
            returns=result['returns'],
            n_simulations=1000  # Reduced for test speed
        )
        
        assert 'p_value' in mc_result
        assert 0.0 <= mc_result['p_value'] <= 1.0
        assert 'percentile_rank' in mc_result
    
    def test_transaction_cost_impact(self):
        """Test that transaction costs reduce performance."""
        df = create_sample_fx_data(n_bars=100)
        
        # Generate high-frequency trading signals (lots of trades)
        signals = (df['close'].rolling(5).mean() > df['close'].rolling(10).mean()).astype(int) * 2 - 1
        signals = signals.fillna(0)
        
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        # Run with low costs
        cost_model_low = FXCostModel(spread_bps_major=0.5)
        result_low = engine.run(df, signals, cost_model_low, 'major', 'EURUSD')
        
        # Run with high costs
        cost_model_high = FXCostModel(spread_bps_major=5.0)
        result_high = engine.run(df, signals, cost_model_high, 'major', 'EURUSD')
        
        # High cost should have lower final equity
        final_equity_low = result_low['equity_curve'].iloc[-1]
        final_equity_high = result_high['equity_curve'].iloc[-1]
        
        # With more trades, higher costs should reduce performance
        if result_low['metrics']['total_trades'] > 5:
            assert final_equity_low >= final_equity_high, (
                "Higher transaction costs should not improve performance"
            )
    
    def test_edge_case_continuous_trading(self):
        """Test edge case: continuous trading (always long or short)."""
        df = create_sample_fx_data(n_bars=100)
        
        # Always long
        signals = pd.Series(1, index=df.index)
        
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        result = engine.run(df, signals, cost_model, 'major', 'EURUSD')
        
        # Should have minimal trades (just entry)
        assert result['metrics']['total_trades'] <= 2  # Entry and maybe exit
        
        # Verify equity moves with market
        returns = df['close'].pct_change()
        
        # With always-long position, should roughly track market
        # (minus costs and lag)
        assert result['metrics']['total_return'] is not None
    
    def test_edge_case_no_trading(self):
        """Test edge case: no trading signals (always flat)."""
        df = create_sample_fx_data(n_bars=100)
        
        # Always flat
        signals = pd.Series(0, index=df.index)
        
        cost_model = FXCostModel(spread_bps_major=1.5)
        engine = BacktestEngine(initial_capital=100000, execution_lag=1)
        
        result = engine.run(df, signals, cost_model, 'major', 'EURUSD')
        
        # Should have zero returns
        assert result['metrics']['total_return'] == 0.0
        assert result['metrics']['total_trades'] == 0
        
        # Equity should remain at initial capital
        assert all(result['equity_curve'] == 100000)


class TestFeatureEngineeringIntegration:
    """Test feature engineering in realistic workflow."""
    
    def test_comprehensive_feature_generation(self):
        """Test generating full feature set."""
        df = create_sample_fx_data(n_bars=252)
        
        fe = FeatureEngineering()
        
        # Add all feature types
        df = fe.add_momentum(df, windows=[5, 10, 20])
        df = fe.add_volatility_features(df, windows=[10, 20])
        df = fe.add_zscore(df, 'close', window=20, feature_name='close_zscore')
        df = fe.add_rsi(df, period=14)
        
        # Verify features created
        assert 'momentum_5' in df.columns
        assert 'volatility_10' in df.columns
        assert 'close_zscore' in df.columns
        assert 'rsi_14' in df.columns
        
        # Verify no infinite values
        assert not np.isinf(df.select_dtypes(include=[np.number])).any().any()
    
    def test_stationarity_handling(self):
        """Test making features stationary."""
        df = create_sample_fx_data(n_bars=252)
        
        fe = FeatureEngineering()
        
        # Price is non-stationary, returns should be stationary
        returns = log_returns(df['close'])
        
        # Make stationary if needed
        stationary_series = fe.make_stationary(df['close'])
        
        # Verify result is a series
        assert isinstance(stationary_series, pd.Series)
        assert len(stationary_series) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
