"""
Full backtest execution with transaction costs and risk management.

Implements complete strategy lifecycle:
1. Load data and generate features
2. Generate exhaustion-failure signals
3. Size positions with 1% fractional risk
4. Apply trailing stops and time exits
5. Account for transaction costs (spread, slippage, impact)
6. Track detailed trade-level metrics
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.features.library import FeatureEngineering
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.backtest.position_sizer import (
    FXPairManager,
    PositionSizer,
    TrailingStopManager,
    TimeExitManager,
    calculate_profit_pips,
    calculate_profit_dollars
)
from src.backtest.cost_model import TransactionCostModel


@dataclass
class Trade:
    """Individual trade record."""
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    pair: str
    direction: int  # 1 = long, -1 = short
    entry_price: float
    exit_price: float
    position_size: float
    stop_pips: float
    profit_pips: float
    profit_dollars: float
    exit_reason: str  # 'stop_loss', 'trailing_stop', 'time_exit', 'profit_target'
    bars_held: int
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    total_cost: float = 0.0


@dataclass
class BacktestResults:
    """Complete backtest results."""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    metrics: Dict = field(default_factory=dict)
    pair: str = ""
    

def execute_backtest(
    df: pd.DataFrame,
    pair: str,
    strategy: ExhaustionFailureStrategy,
    initial_capital: float = 100000.0,
    stop_pips: float = 10.0,
    fixed_target_pips: float = 15.0,
    use_trailing_stop: bool = True,
    max_bars_held: int = 5,
    apply_costs: bool = True
) -> BacktestResults:
    """
    Execute complete backtest with risk management.
    
    Args:
        df: OHLCV data with features
        pair: Pair name (e.g., 'USDJPY')
        strategy: Strategy instance
        initial_capital: Starting capital
        stop_pips: Initial stop loss in pips
        fixed_target_pips: Fixed profit target in pips (optional)
        use_trailing_stop: Whether to use 4/3 trailing stop
        max_bars_held: Maximum bars to hold position
        apply_costs: Whether to apply transaction costs
        
    Returns:
        BacktestResults with trades and metrics
    """
    # Initialize managers
    fx_manager = FXPairManager()
    position_sizer = PositionSizer(fx_manager)
    trail_manager = TrailingStopManager(fx_manager, trigger_pips=4, trail_distance_pips=3)
    time_manager = TimeExitManager(max_bars=max_bars_held)
    cost_model = TransactionCostModel() if apply_costs else None
    
    # Generate signals
    signals = strategy.generate_signals(df)
    df['signal'] = signals
    
    # Track state
    capital = initial_capital
    position = None  # Current open position
    trades = []
    equity = [capital]
    
    for i in range(len(df)):
        current_bar = df.iloc[i]
        current_time = df.index[i]
        
        # Check if in position
        if position is not None:
            # Update trailing stop
            if use_trailing_stop:
                current_stop = trail_manager.update_stop(
                    entry_price=position['entry_price'],
                    current_price=current_bar['close'],
                    pair=pair,
                    direction=position['direction'],
                    initial_stop_pips=stop_pips,
                    trade_id=position['trade_id']
                )
            else:
                current_stop = position['stop_price']
            
            # Check stop loss
            stop_hit = False
            if position['direction'] == 1:  # Long
                stop_hit = current_bar['low'] <= current_stop
            else:  # Short
                stop_hit = current_bar['high'] >= current_stop
            
            # Check profit target
            target_hit = False
            if fixed_target_pips > 0:
                profit_pips = calculate_profit_pips(
                    position['entry_price'],
                    current_bar['close'],
                    pair,
                    position['direction'],
                    fx_manager
                )
                target_hit = profit_pips >= fixed_target_pips
            
            # Check time exit
            time_exit = time_manager.check_exit(
                position['entry_bar'],
                i
            )
            
            # Exit if any condition met
            exit_reason = None
            exit_price = current_bar['close']
            
            if stop_hit:
                exit_reason = 'trailing_stop' if trail_manager.is_active.get(position['trade_id'], False) else 'stop_loss'
                exit_price = current_stop
            elif target_hit:
                exit_reason = 'profit_target'
            elif time_exit:
                exit_reason = 'time_exit'
            
            if exit_reason is not None:
                # Calculate profit
                profit_pips = calculate_profit_pips(
                    position['entry_price'],
                    exit_price,
                    pair,
                    position['direction'],
                    fx_manager
                )
                profit_dollars = calculate_profit_dollars(
                    position['entry_price'],
                    exit_price,
                    position['size'],
                    pair,
                    position['direction'],
                    fx_manager
                )
                
                # Apply costs
                spread_cost = 0.0
                slippage_cost = 0.0
                if apply_costs and cost_model is not None:
                    # Entry + exit spread
                    spread_cost = cost_model.calculate_spread_cost(
                        position['size'],
                        position['entry_price'],
                        pair
                    ) * 2
                    
                    # Slippage (approximate)
                    vol = df['close'].pct_change().std()
                    avg_volume = df['volume'].mean() if 'volume' in df.columns else 1000000
                    slippage_cost = cost_model.calculate_slippage(
                        position['size'],
                        vol,
                        avg_volume
                    ) * position['entry_price'] * position['size']
                
                total_cost = spread_cost + slippage_cost
                net_profit = profit_dollars - total_cost
                
                # Record trade
                trade = Trade(
                    entry_time=position['entry_time'],
                    exit_time=current_time,
                    pair=pair,
                    direction=position['direction'],
                    entry_price=position['entry_price'],
                    exit_price=exit_price,
                    position_size=position['size'],
                    stop_pips=stop_pips,
                    profit_pips=profit_pips,
                    profit_dollars=net_profit,
                    exit_reason=exit_reason,
                    bars_held=i - position['entry_bar'],
                    spread_cost=spread_cost,
                    slippage_cost=slippage_cost,
                    total_cost=total_cost
                )
                trades.append(trade)
                
                # Update capital
                capital += net_profit
                
                # Clear position
                position = None
        
        # Check for new signal (only if not in position)
        if position is None and i < len(df) - 1:  # Need next bar to enter
            signal = signals.iloc[i]
            
            if signal != 0:
                # Enter on next bar open (1-bar execution lag)
                next_bar = df.iloc[i + 1]
                entry_price = next_bar['open']
                
                # Size position
                position_size = position_sizer.calculate_position_size(
                    capital=capital,
                    stop_pips=stop_pips,
                    pair=pair,
                    risk_pct=0.01
                )
                
                # Calculate stop price
                direction = int(signal)
                if direction == 1:  # Long
                    stop_price = entry_price - fx_manager.pips_to_price(stop_pips, pair)
                else:  # Short
                    stop_price = entry_price + fx_manager.pips_to_price(stop_pips, pair)
                
                # Open position
                trade_id = len(trades)
                position = {
                    'entry_time': df.index[i + 1],
                    'entry_bar': i + 1,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'direction': direction,
                    'size': position_size,
                    'trade_id': trade_id
                }
                
                # Reset trailing stop
                trail_manager.reset(trade_id)
                
                # Skip to next bar
                continue
        
        # Update equity curve
        if position is not None:
            # Mark-to-market
            mtm_profit = calculate_profit_dollars(
                position['entry_price'],
                current_bar['close'],
                position['size'],
                pair,
                position['direction'],
                fx_manager
            )
            equity.append(capital + mtm_profit)
        else:
            equity.append(capital)
    
    # Create results
    equity_curve = pd.Series(equity, index=df.index[:len(equity)])
    
    # Calculate metrics
    metrics = calculate_metrics(trades, equity_curve, initial_capital)
    
    return BacktestResults(
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        pair=pair
    )


def calculate_metrics(trades: List[Trade], equity_curve: pd.Series, initial_capital: float) -> Dict:
    """Calculate performance metrics."""
    if len(trades) == 0:
        return {'error': 'No trades executed'}
    
    # Trade-level metrics
    n_trades = len(trades)
    winners = [t for t in trades if t.profit_dollars > 0]
    losers = [t for t in trades if t.profit_dollars <= 0]
    
    n_winners = len(winners)
    n_losers = len(losers)
    win_rate = n_winners / n_trades if n_trades > 0 else 0
    
    total_profit = sum(t.profit_dollars for t in trades)
    avg_profit = total_profit / n_trades
    avg_winner = np.mean([t.profit_dollars for t in winners]) if winners else 0
    avg_loser = np.mean([t.profit_dollars for t in losers]) if losers else 0
    
    profit_factor = abs(sum(t.profit_dollars for t in winners) / sum(t.profit_dollars for t in losers)) if losers and sum(t.profit_dollars for t in losers) != 0 else np.inf
    
    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1
    
    # Equity curve metrics
    returns = equity_curve.pct_change().dropna()
    total_return = (equity_curve.iloc[-1] - initial_capital) / initial_capital
    
    if len(returns) > 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 24) if returns.std() > 0 else 0  # Hourly to annual
        downside_returns = returns[returns < 0]
        sortino = returns.mean() / downside_returns.std() * np.sqrt(252 * 24) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        
        # Max drawdown
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        max_drawdown = drawdown.min()
        
        calmar = (total_return / abs(max_drawdown)) if max_drawdown != 0 else 0
    else:
        sharpe = sortino = max_drawdown = calmar = 0
    
    # Cost analysis
    total_costs = sum(t.total_cost for t in trades)
    cost_per_trade = total_costs / n_trades if n_trades > 0 else 0
    
    return {
        'n_trades': n_trades,
        'n_winners': n_winners,
        'n_losers': n_losers,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit_per_trade': avg_profit,
        'avg_winner': avg_winner,
        'avg_loser': avg_loser,
        'profit_factor': profit_factor,
        'total_return_pct': total_return * 100,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'max_drawdown_pct': max_drawdown * 100,
        'calmar_ratio': calmar,
        'total_costs': total_costs,
        'cost_per_trade': cost_per_trade,
        'exit_reasons': exit_reasons
    }


def main():
    """Run full backtest on all pairs."""
    print("="*80)
    print("EXHAUSTION-FAILURE STRATEGY: FULL BACKTEST")
    print("="*80)
    
    # Paths
    project_root = Path( __file__).parent.parent
    data_dir = project_root / "data" / "raw"
    config_path = project_root / "config" / "config.yaml"
    
    # Initialize strategy
    strategy = ExhaustionFailureStrategy.from_config(str(config_path))
    
    # Test on key pairs
    test_pairs = ['NZDJPY', 'USDJPY', 'EURUSD', 'GBPUSD']
    
    all_results = {}
    
    for pair in test_pairs:
        print(f"\n{'='*80}")
        print(f"Backtesting {pair}")
        print(f"{'='*80}")
        
        try:
            # Load data
            loader = FXDataLoader()
            csv_path = data_dir / f"{pair}60.csv"
            df, metadata = loader.load_csv(str(csv_path), pair=pair)
            
            if df is None or len(df) < 100:
                print(f"✗ Insufficient data for {pair}")
                continue
            
            print(f"Loaded {len(df)} bars")
            
            # Add features
            fe = FeatureEngineering()
            df_features = df.copy()
            df_features = fe.add_momentum(df_features, windows=[5, 10, 20])
            df_features = fe.add_volatility_features(df_features)
            df_features = fe.add_range_features(df_features, windows=[10, 20, 50])
            df_features = fe.add_close_position(df_features)
            df_features = fe.add_consecutive_direction(df_features, windows=[2, 3])
            df_features = fe.add_range_breakout_features(df_features, windows=[10, 20, 50])
            
            # Run backtest
            results = execute_backtest(
                df=df_features,
                pair=pair,
                strategy=strategy,
                initial_capital=100000.0,
                stop_pips=10.0,
                fixed_target_pips=15.0,
                use_trailing_stop=True,
                max_bars_held=5,
                apply_costs=True
            )
            
            all_results[pair] = results
            
            # Print metrics
            m = results.metrics
            print(f"\nPerformance Metrics:")
            print(f"  Total trades: {m['n_trades']}")
            print(f"  Win rate: {m['win_rate']:.2%}")
            print(f"  Total return: {m['total_return_pct']:.2f}%")
            print(f"  Sharpe ratio: {m['sharpe_ratio']:.2f}")
            print(f"  Sortino ratio: {m['sortino_ratio']:.2f}")
            print(f"  Max drawdown: {m['max_drawdown_pct']:.2f}%")
            print(f"  Profit factor: {m['profit_factor']:.2f}")
            print(f"  Avg profit/trade: ${m['avg_profit_per_trade']:.2f}")
            print(f"  Total costs: ${m['total_costs']:.2f} (${m['cost_per_trade']:.2f}/trade)")
            
            print(f"\nExit Reason Breakdown:")
            for reason, count in m['exit_reasons'].items():
                pct = count / m['n_trades'] * 100
                print(f"  {reason}: {count} ({pct:.1f}%)")
            
        except Exception as e:
            print(f"✗ Error backtesting {pair}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary across all pairs
    print(f"\n{'='*80}")
    print("SUMMARY ACROSS ALL PAIRS")
    print(f"{'='*80}")
    
    summary_data = []
    for pair, results in all_results.items():
        m = results.metrics
        summary_data.append({
            'Pair': pair,
            'Trades': m['n_trades'],
            'Win Rate': f"{m['win_rate']:.1%}",
            'Return': f"{m['total_return_pct']:.1f}%",
            'Sharpe': f"{m['sharpe_ratio']:.2f}",
            'Max DD': f"{m['max_drawdown_pct']:.1f}%",
            'Profit Factor': f"{m['profit_factor']:.2f}"
        })
    
    summary_df = pd.DataFrame(summary_data)
    print("\n" + summary_df.to_string(index=False))
    
    # Save results
    output_dir = project_root / "reports"
    output_dir.mkdir(exist_ok=True)
    
    summary_df.to_csv(output_dir / "backtest_summary.csv", index=False)
    print(f"\n✓ Summary saved to {output_dir / 'backtest_summary.csv'}")
    
    # Save detailed trades
    for pair, results in all_results.items():
        trades_data = []
        for t in results.trades:
            trades_data.append({
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'direction': 'LONG' if t.direction == 1 else 'SHORT',
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'profit_pips': t.profit_pips,
                'profit_dollars': t.profit_dollars,
                'exit_reason': t.exit_reason,
                'bars_held': t.bars_held,
                'total_cost': t.total_cost
            })
        
        trades_df = pd.DataFrame(trades_data)
        trades_df.to_csv(output_dir / f"trades_{pair}.csv", index=False)
    
    print(f"✓ Trade details saved to {output_dir}/trades_*.csv")
    
    print("\n" + "="*80)
    
    return all_results


if __name__ == "__main__":
    results = main()
