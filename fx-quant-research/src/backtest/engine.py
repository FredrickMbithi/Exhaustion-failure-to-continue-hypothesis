"""
Vectorized backtest engine for FX strategies.

Implements custom vectorized backtesting with:
- Proper 1-bar execution lag (no lookahead bias)
- Transaction cost integration
- Comprehensive performance metrics
- Full reproducibility
"""

from typing import Dict, TypedDict, Optional, List

import numpy as np
import pandas as pd

from .cost_model import FXCostModel


class BacktestResult(TypedDict):
    """Structured backtest results."""
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    positions: pd.Series
    trades: pd.Series
    returns: pd.Series
    cost_breakdown: pd.DataFrame
    metrics: Dict[str, float]


class BacktestEngine:
    """
    Vectorized backtest engine with proper lag handling.
    
    Critical feature: Enforces 1-bar execution lag to prevent lookahead bias.
    Signal at time t can only be executed at time t+1.
    
    Examples:
        >>> engine = BacktestEngine(initial_capital=100000)
        >>> result = engine.run(data=df, signals=signals, cost_model=cost_model)
        >>> print(f"Sharpe Ratio: {result['metrics']['sharpe']:.2f}")
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        execution_lag: int = 1,
        annualization_factor: int = 252
    ):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital
            execution_lag: Number of bars between signal and execution (default: 1)
            annualization_factor: For metrics (252 for daily, 252*24 for hourly)
        """
        self.initial_capital = initial_capital
        self.execution_lag = execution_lag
        self.annualization_factor = annualization_factor
    
    def run(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        cost_model: Optional[FXCostModel] = None,
        pair_tier: str = 'major',
        pair_name: str = 'UNKNOWN'
    ) -> BacktestResult:
        """
        Run vectorized backtest.
        
        Args:
            data: DataFrame with OHLC data and DatetimeIndex
            signals: Series with trading signals (-1, 0, 1) aligned with data
            cost_model: Transaction cost model (optional)
            pair_tier: Currency pair tier for cost calculation
            pair_name: Currency pair name
            
        Returns:
            BacktestResult with equity curve, metrics, and analysis
            
        Raises:
            ValueError: If data and signals don't align
            
        Examples:
            >>> # Generate simple SMA crossover signals
            >>> signals = (df['close'].rolling(10).mean() > df['close'].rolling(50).mean()).astype(int) * 2 - 1
            >>> result = engine.run(data=df, signals=signals, cost_model=cost_model)
        """
        # Validate inputs
        if not data.index.equals(signals.index):
            raise ValueError("Data and signals indices must be aligned")
        
        if len(data) < 2:
            raise ValueError("Need at least 2 bars of data for backtesting")
        
        # CRITICAL: Apply execution lag to avoid lookahead bias
        # Signal at time t can only be executed at time t+1
        positions = signals.shift(self.execution_lag).fillna(0)
        
        # Calculate returns
        returns = data['close'].pct_change()
        
        # Calculate gross strategy returns
        # Position determined at t-1, earns return from t-1 to t
        gross_returns = positions.shift(1) * returns
        
        # Calculate position changes (trades)
        trades = positions.diff().abs()
        
        # Apply transaction costs
        cost_series = pd.Series(0.0, index=data.index)
        cost_breakdown_list = []
        
        if cost_model is not None:
            # Calculate volume and volatility for cost model
            avg_volume = data['volume'].rolling(window=20, min_periods=1).mean()
            volatility = returns.rolling(window=20, min_periods=1).std()
            
            for timestamp, trade_size in trades[trades > 0].items():
                idx = data.index.get_loc(timestamp)
                
                if idx > 0:  # Skip first bar
                    price = data['close'].iloc[idx]
                    vol = avg_volume.iloc[idx] if not pd.isna(avg_volume.iloc[idx]) else 1e6
                    vola = volatility.iloc[idx] if not pd.isna(volatility.iloc[idx]) else 0.01
                    
                    # Determine side (buy or sell)
                    position_change = positions.iloc[idx] - positions.iloc[idx - 1]
                    side = 'buy' if position_change > 0 else 'sell'
                    
                    # Calculate costs
                    costs = cost_model.total_cost(
                        price=price,
                        size=abs(trade_size * self.initial_capital / price),  # Convert to notional
                        side=side,
                        pair_tier=pair_tier,
                        volume=vol,
                        volatility=vola,
                        timestamp=timestamp,
                        pair=pair_name
                    )
                    
                    # Store cost as fraction of capital
                    cost_series.loc[timestamp] = costs['total'] / self.initial_capital
                    
                    # Store breakdown
                    cost_breakdown_list.append({
                        'timestamp': timestamp,
                        'trade_size': trade_size,
                        'price': price,
                        'spread': costs['spread'] / self.initial_capital,
                        'slippage': costs['slippage'] / self.initial_capital,
                        'impact': costs['impact'] / self.initial_capital,
                        'swap': costs['swap'] / self.initial_capital,
                        'total': costs['total'] / self.initial_capital,
                        'bps': costs['bps']
                    })
        
        # Calculate net returns
        net_returns = gross_returns - cost_series
        
        # Build equity curve
        equity_curve = (1 + net_returns).cumprod() * self.initial_capital
        
        # Calculate drawdown
        running_max = equity_curve.expanding().max()
        drawdown_curve = (equity_curve - running_max) / running_max
        
        # Create cost breakdown DataFrame
        if cost_breakdown_list:
            cost_breakdown = pd.DataFrame(cost_breakdown_list).set_index('timestamp')
        else:
            cost_breakdown = pd.DataFrame()
        
        # Calculate metrics
        metrics = self._calculate_metrics(
            net_returns=net_returns,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades,
            positions=positions
        )
        
        return BacktestResult(
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            positions=positions,
            trades=trades,
            returns=net_returns,
            cost_breakdown=cost_breakdown,
            metrics=metrics
        )
    
    def _calculate_metrics(
        self,
        net_returns: pd.Series,
        equity_curve: pd.Series,
        drawdown_curve: pd.Series,
        trades: pd.Series,
        positions: pd.Series
    ) -> Dict[str, float]:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            net_returns: Net returns series
            equity_curve: Equity curve
            drawdown_curve: Drawdown curve
            trades: Trade sizes
            positions: Position series
            
        Returns:
            Dictionary of performance metrics
        """
        metrics = {}
        
        # Basic stats
        total_bars = len(net_returns)
        non_zero_returns = net_returns[net_returns != 0]
        
        if len(non_zero_returns) == 0:
            # No trades executed
            return {
                'total_return': 0.0,
                'cagr': 0.0,
                'sharpe': 0.0,
                'sortino': 0.0,
                'max_drawdown': 0.0,
                'calmar': 0.0,
                'win_rate': 0.0,
                'total_trades': 0,
                'turnover': 0.0
            }
        
        # Total return
        final_value = equity_curve.iloc[-1]
        initial_value = equity_curve.iloc[0]
        total_return = (final_value / initial_value) - 1
        metrics['total_return'] = float(total_return)
        
        # CAGR
        years = total_bars / self.annualization_factor
        if years > 0 and final_value > 0 and initial_value > 0:
            cagr = (final_value / initial_value) ** (1 / years) - 1
        else:
            cagr = 0.0
        metrics['cagr'] = float(cagr)
        
        # Sharpe ratio
        mean_return = net_returns.mean()
        std_return = net_returns.std()
        if std_return > 0:
            sharpe = (mean_return / std_return) * np.sqrt(self.annualization_factor)
        else:
            sharpe = 0.0
        metrics['sharpe'] = float(sharpe)
        
        # Sortino ratio (downside deviation)
        downside_returns = net_returns[net_returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std()
            if downside_std > 0:
                sortino = (mean_return / downside_std) * np.sqrt(self.annualization_factor)
            else:
                sortino = 0.0
        else:
            sortino = sharpe  # No downside, use Sharpe
        metrics['sortino'] = float(sortino)
        
        # Maximum drawdown
        max_dd = drawdown_curve.min()
        metrics['max_drawdown'] = float(max_dd)
        
        # Calmar ratio
        if max_dd < 0:
            calmar = cagr / abs(max_dd)
        else:
            calmar = 0.0
        metrics['calmar'] = float(calmar)
        
        # Win rate
        winning_days = (net_returns > 0).sum()
        losing_days = (net_returns < 0).sum()
        trade_days = winning_days + losing_days
        if trade_days > 0:
            win_rate = winning_days / trade_days
        else:
            win_rate = 0.0
        metrics['win_rate'] = float(win_rate)
        
        # Trade count
        total_trades = (trades > 0).sum()
        metrics['total_trades'] = int(total_trades)
        
        # Turnover
        mean_position = positions.abs().mean()
        if mean_position > 0 and total_bars > 0:
            turnover = trades.sum() / total_bars
        else:
            turnover = 0.0
        metrics['turnover'] = float(turnover)
        
        # Additional metrics
        metrics['avg_return'] = float(net_returns.mean())
        metrics['std_return'] = float(net_returns.std())
        metrics['skewness'] = float(net_returns.skew()) if len(net_returns) > 2 else 0.0
        metrics['kurtosis'] = float(net_returns.kurtosis()) if len(net_returns) > 3 else 0.0
        
        return metrics


def print_backtest_summary(result: BacktestResult) -> None:
    """
    Print formatted backtest summary.
    
    Args:
        result: BacktestResult from engine.run()
        
    Examples:
        >>> result = engine.run(data, signals, cost_model)
        >>> print_backtest_summary(result)
    """
    metrics = result['metrics']
    
    print("\n" + "="*60)
    print("BACKTEST SUMMARY")
    print("="*60)
    
    print(f"\nPerformance Metrics:")
    print(f"  Total Return:    {metrics['total_return']:>10.2%}")
    print(f"  CAGR:            {metrics['cagr']:>10.2%}")
    print(f"  Sharpe Ratio:    {metrics['sharpe']:>10.2f}")
    print(f"  Sortino Ratio:   {metrics['sortino']:>10.2f}")
    print(f"  Calmar Ratio:    {metrics['calmar']:>10.2f}")
    
    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown:    {metrics['max_drawdown']:>10.2%}")
    print(f"  Volatility:      {metrics['std_return']:>10.4f}")
    print(f"  Skewness:        {metrics['skewness']:>10.2f}")
    print(f"  Kurtosis:        {metrics['kurtosis']:>10.2f}")
    
    print(f"\nTrading Activity:")
    print(f"  Total Trades:    {metrics['total_trades']:>10}")
    print(f"  Win Rate:        {metrics['win_rate']:>10.2%}")
    print(f"  Turnover:        {metrics['turnover']:>10.2f}")
    
    print("\n" + "="*60 + "\n")
