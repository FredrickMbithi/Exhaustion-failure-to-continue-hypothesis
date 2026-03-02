"""
Example: Simple FX backtest with data quality checks and performance attribution.

This example demonstrates the complete workflow:
1. Load and validate data
2. Generate quality report
3. Engineer features
4. Run backtest with transaction costs
5. Analyze performance attribution
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.loader import FXDataLoader
from src.data.validator import DataValidator
from src.data.forensics import DataForensics
from src.features.library import FeatureEngineering
from src.backtest.engine import BacktestEngine, print_backtest_summary
from src.backtest.cost_model import FXCostModel
from src.backtest.seed_manager import set_global_seed
from src.analysis.attribution import PerformanceAttribution
from src.utils.environment import load_config


def create_demo_data():
    """Create demo FX data for illustration."""
    print("📊 Creating demo FX data...")
    
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', '2022-12-31', freq='D', tz='UTC')
    
    # Simulate realistic FX price action
    returns = np.random.randn(len(dates)) * 0.008  # 0.8% daily vol
    log_prices = np.log(1.1200) + np.cumsum(returns)
    close = np.exp(log_prices)
    
    # Generate OHLC
    intraday_range = np.abs(np.random.randn(len(dates))) * 0.003
    open_prices = close * (1 + np.random.randn(len(dates)) * 0.002)
    high = np.maximum(open_prices, close) * (1 + intraday_range)
    low = np.minimum(open_prices, close) * (1 - intraday_range)
    
    volume = np.random.uniform(1_000_000, 5_000_000, len(dates))
    spread = np.random.uniform(0.00008, 0.00012, len(dates))  # ~1 pip
    
    df = pd.DataFrame({
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'spread': spread
    }, index=dates)
    
    print(f"✓ Created {len(df)} bars of EURUSD data")
    return df


def main():
    """Run example backtest."""
    
    print("\n" + "="*70)
    print("FX QUANTITATIVE RESEARCH FRAMEWORK - EXAMPLE")
    print("="*70 + "\n")
    
    # Set seed for reproducibility
    set_global_seed(42)
    
    # Step 1: Load data
    print("1️⃣  Loading Data")
    print("-" * 70)
    df = create_demo_data()
    
    # Step 2: Validate data quality
    print("\n2️⃣  Validating Data Quality")
    print("-" * 70)
    validator = DataValidator(spike_threshold=5.0)
    report = validator.validate(df, pair="EURUSD")
    
    if report.is_valid:
        print("✓ Data validation passed")
    else:
        print("⚠  Validation issues detected:")
        for error in report.errors[:3]:
            print(f"  - {error}")
    
    print(f"\nData Quality Metrics:")
    print(f"  Total bars: {report.metrics.get('total_bars', 0)}")
    print(f"  Missing bars: {report.metrics.get('missing_bars', 0)}")
    print(f"  Spike count: {report.metrics.get('spike_count', 0)}")
    
    # Step 3: Generate forensics report
    print("\n3️⃣  Generating Forensics Report")
    print("-" * 70)
    forensics = DataForensics()
    quality_report = forensics.generate_report(df, "EURUSD")
    
    quality_score = quality_report['quality_score']
    if quality_score >= 90:
        emoji = "🟢"
    elif quality_score >= 70:
        emoji = "🟡"
    else:
        emoji = "🔴"
    
    print(f"{emoji} Data Quality Score: {quality_score:.1f}/100")
    
    # Step 4: Engineer features
    print("\n4️⃣  Engineering Features")
    print("-" * 70)
    fe = FeatureEngineering()
    
    df = fe.add_momentum(df, windows=[10, 20, 50])
    df = fe.add_volatility_features(df, windows=[20])
    df = fe.add_rsi(df, period=14)
    
    print(f"✓ Generated features:")
    print(f"  - Momentum (10, 20, 50-day)")
    print(f"  - Volatility (20-day)")
    print(f"  - RSI (14-period)")
    
    # Step 5: Generate trading signals
    print("\n5️⃣  Generating Trading Signals")
    print("-" * 70)
    
    # Strategy: SMA crossover with RSI filter
    sma_fast = df['close'].rolling(10).mean()
    sma_slow = df['close'].rolling(50).mean()
    
    # Long when fast > slow and RSI not overbought
    long_signal = (sma_fast > sma_slow) & (df['rsi_14'] < 70)
    
    # Short when fast < slow and RSI not oversold
    short_signal = (sma_fast < sma_slow) & (df['rsi_14'] > 30)
    
    df['signal'] = 0
    df.loc[long_signal, 'signal'] = 1
    df.loc[short_signal, 'signal'] = -1
    
    print(f"✓ Strategy: SMA(10/50) crossover with RSI filter")
    print(f"  Long signals: {(df['signal'] == 1).sum()}")
    print(f"  Short signals: {(df['signal'] == -1).sum()}")
    print(f"  Flat: {(df['signal'] == 0).sum()}")
    
    # Step 6: Run backtest
    print("\n6️⃣  Running Backtest")
    print("-" * 70)
    
    cost_model = FXCostModel(
        spread_bps_major=1.5,
        slippage_coefficient=0.1,
        market_impact_exponent=0.5
    )
    
    engine = BacktestEngine(
        initial_capital=100_000,
        execution_lag=1
    )
    
    result = engine.run(
        data=df,
        signals=df['signal'],
        cost_model=cost_model,
        pair_tier='major',
        pair_name='EURUSD'
    )
    
    print_backtest_summary(result)
    
    # Step 7: Performance attribution
    print("\n7️⃣  Performance Attribution")
    print("-" * 70)
    
    attribution = PerformanceAttribution()
    
    # Monte Carlo significance test (reduced simulations for demo)
    mc_result = attribution.monte_carlo_pvalue(
        strategy_sharpe=result['metrics']['sharpe'],
        returns=result['returns'],
        n_simulations=5000
    )
    
    print(f"\nMonte Carlo Significance Test ({mc_result['n_simulations']:,} simulations):")
    print(f"  Strategy Sharpe: {mc_result['strategy_sharpe']:.3f}")
    print(f"  Average Random Sharpe: {mc_result['random_sharpe_mean']:.3f}")
    print(f"  p-value: {mc_result['p_value']:.4f}")
    print(f"  Percentile: {mc_result['percentile_rank']:.1f}%")
    
    if mc_result['is_significant_5pct']:
        print(f"  ✓ Strategy is statistically significant at 5% level")
    else:
        print(f"  ⚠ Strategy is NOT statistically significant")
    
    # Cost attribution
    cost_report = attribution.cost_attribution(
        gross_returns=result['returns'],  # Simplified
        net_returns=result['returns'],
        cost_breakdown=result['cost_breakdown']
    )
    
    print(f"\nTransaction Cost Impact:")
    print(f"  Total cost: {cost_report['total_cost_bps']:.2f} bps")
    print(f"  Annualized cost: {cost_report['annualized_cost_bps']:.2f} bps/year")
    
    # Step 8: Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n📈 Strategy Performance:")
    print(f"   Total Return: {result['metrics']['total_return']:.2%}")
    print(f"   Annualized Return: {result['metrics']['annualized_return']:.2%}")
    print(f"   Sharpe Ratio: {result['metrics']['sharpe']:.2f}")
    print(f"   Max Drawdown: {result['metrics']['max_drawdown']:.2%}")
    
    print(f"\n📊 Trading Activity:")
    print(f"   Total Trades: {result['metrics']['total_trades']}")
    print(f"   Turnover: {result['metrics']['turnover']:.2f}")
    print(f"   Win Rate: {result['metrics']['win_rate']:.2%}")
    
    print(f"\n💰 Risk-Adjusted Performance:")
    print(f"   Sortino Ratio: {result['metrics']['sortino']:.2f}")
    print(f"   Calmar Ratio: {result['metrics']['calmar']:.2f}")
    
    print(f"\n✅ Backtest completed successfully!")
    print(f"   - Proper 1-bar execution lag enforced")
    print(f"   - Realistic transaction costs applied")
    print(f"   - No lookahead bias")
    print(f"   - Fully reproducible (seed=42)")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
