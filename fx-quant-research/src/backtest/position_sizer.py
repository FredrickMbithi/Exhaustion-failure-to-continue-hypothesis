"""
Position sizing and risk management for FX trading.

Implements:
- Fractional risk position sizing (1% capital risk per trade)
- Trailing stop management (4-pip trigger, 3-pip trail)
- Time-based exits (max hold period)
- Pip conversion utilities (pair-specific)

References:
    User specification: Fixed fractional sizing with 10-pip stops
    Formula: size = (capital × 0.01) / (stop_pips × pip_size)
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml


@dataclass
class PairConfig:
    """Configuration for a specific FX pair."""
    pip_size: float
    pip_value: float
    tier: str
    spread_bps: float
    description: str


class FXPairManager:
    """
    Manages FX pair-specific configurations.
    
    Loads pip sizes, pip values, spreads, and tiers from configuration.
    Provides utility functions for pip conversions.
    
    Examples:
        >>> manager = FXPairManager()
        >>> pip_size = manager.get_pip_size('USDJPY')
        >>> price_move = manager.pips_to_price(10, 'USDJPY')
    """
    
    def __init__(self, config_path: str = "config/fx_pairs.yaml"):
        """
        Initialize pair manager from configuration.
        
        Args:
            config_path: Path to FX pairs configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pairs: Dict[str, PairConfig] = {}
        for pair_name, pair_data in config.get('pairs', {}).items():
            self.pairs[pair_name] = PairConfig(
                pip_size=pair_data['pip_size'],
                pip_value=pair_data['pip_value'],
                tier=pair_data['tier'],
                spread_bps=pair_data['spread_bps'],
                description=pair_data.get('description', '')
            )
        
        self.tier_defaults = config.get('tier_defaults', {})
        self.position_sizing_params = config.get('position_sizing', {})
        self.risk_params = config.get('risk_management', {})
    
    def get_pip_size(self, pair: str) -> float:
        """
        Get pip size for a pair.
        
        Args:
            pair: FX pair name (e.g., 'USDJPY', 'EURUSD')
            
        Returns:
            Pip size (0.01 for JPY pairs, 0.0001 for most others)
            
        Raises:
            KeyError: If pair not found in configuration
            
        Examples:
            >>> manager.get_pip_size('USDJPY')
            0.01
            >>> manager.get_pip_size('EURUSD')
            0.0001
        """
        if pair not in self.pairs:
            raise KeyError(f"Pair '{pair}' not found in configuration")
        return self.pairs[pair].pip_size
    
    def get_pip_value(self, pair: str) -> float:
        """Get pip value (USD per pip for standard lot)."""
        if pair not in self.pairs:
            raise KeyError(f"Pair '{pair}' not found in configuration")
        return self.pairs[pair].pip_value
    
    def get_tier(self, pair: str) -> str:
        """Get liquidity tier ('major', 'minor', 'exotic')."""
        if pair not in self.pairs:
            raise KeyError(f"Pair '{pair}' not found in configuration")
        return self.pairs[pair].tier
    
    def get_spread_bps(self, pair: str) -> float:
        """Get typical spread in basis points."""
        if pair not in self.pairs:
            raise KeyError(f"Pair '{pair}' not found in configuration")
        return self.pairs[pair].spread_bps
    
    def pips_to_price(self, pips: float, pair: str) -> float:
        """
        Convert pips to price units.
        
        Args:
            pips: Number of pips
            pair: FX pair name
            
        Returns:
            Price movement equivalent
            
        Examples:
            >>> manager.pips_to_price(10, 'USDJPY')
            0.10  # 10 pips = 0.10 yen
            >>> manager.pips_to_price(10, 'EURUSD')
            0.0010  # 10 pips = 0.0010 dollars
        """
        return pips * self.get_pip_size(pair)
    
    def price_to_pips(self, price_move: float, pair: str) -> float:
        """
        Convert price movement to pips.
        
        Args:
            price_move: Price movement in price units
            pair: FX pair name
            
        Returns:
            Number of pips
            
        Examples:
            >>> manager.price_to_pips(0.10, 'USDJPY')
            10.0
            >>> manager.price_to_pips(0.0010, 'EURUSD')
            10.0
        """
        return price_move / self.get_pip_size(pair)


class PositionSizer:
    """
    Calculate position sizes using fixed fractional risk method.
    
    Formula: size = (capital × risk_pct) / (stop_pips × pip_size)
    
    Default: 1% risk per trade with 10-pip stop
    
    Examples:
        >>> sizer = PositionSizer(pair_manager)
        >>> size = sizer.calculate_position_size(10000, 10, 'USDJPY')
        >>> print(f"Position size: {size:,.2f} units")
    """
    
    def __init__(
        self,
        pair_manager: FXPairManager,
        default_risk_pct: float = 0.01,
        max_position_pct: float = 0.10,
        min_capital: float = 1000.0
    ):
        """
        Initialize position sizer.
        
        Args:
            pair_manager: FXPairManager instance
            default_risk_pct: Risk per trade as fraction of capital (default 1%)
            max_position_pct: Maximum position size as fraction of capital (default 10%)
            min_capital: Minimum account size (default $1,000)
        """
        self.pair_manager = pair_manager
        self.default_risk_pct = default_risk_pct
        self.max_position_pct = max_position_pct
        self.min_capital = min_capital
    
    def calculate_position_size(
        self,
        capital: float,
        stop_pips: float,
        pair: str,
        risk_pct: Optional[float] = None
    ) -> float:
        """
        Calculate position size using fixed fractional risk method.
        
        Args:
            capital: Current account capital (USD)
            stop_pips: Stop loss distance in pips
            pair: FX pair name
            risk_pct: Optional override for risk percentage (default: 1%)
            
        Returns:
            Position size in base currency units
            
        Raises:
            ValueError: If capital below minimum or stop_pips <= 0
            
        Examples:
            >>> # Capital: $10,000, Stop: 10 pips, USDJPY
            >>> size = sizer.calculate_position_size(10000, 10, 'USDJPY')
            >>> # Risk: $100 (1%), Pip size: 0.01
            >>> # Size = 100 / (10 × 0.01) = 1,000 units
            >>> assert size == 1000.0
        """
        # Validation
        if capital < self.min_capital:
            raise ValueError(f"Capital ${capital:,.2f} below minimum ${self.min_capital:,.2f}")
        
        if stop_pips <= 0:
            raise ValueError(f"Stop pips must be positive, got {stop_pips}")
        
        # Calculate risk amount
        risk_pct = risk_pct if risk_pct is not None else self.default_risk_pct
        risk_amount = capital * risk_pct
        
        # Get pip size for pair
        pip_size = self.pair_manager.get_pip_size(pair)
        
        # Calculate position size
        # Formula: size = risk_amount / (stop_pips × pip_size)
        position_size = risk_amount / (stop_pips * pip_size)
        
        # Apply maximum position size constraint
        max_size = capital * self.max_position_pct
        if position_size > max_size:
            position_size = max_size
        
        return round(position_size, 2)
    
    def calculate_risk_amount(
        self,
        position_size: float,
        stop_pips: float,
        pair: str
    ) -> float:
        """
        Calculate dollar risk for a given position and stop.
        
        Args:
            position_size: Position size in units
            stop_pips: Stop loss distance in pips
            pair: FX pair name
            
        Returns:
            Dollar risk amount
            
        Examples:
            >>> risk = sizer.calculate_risk_amount(1000, 10, 'USDJPY')
            >>> assert risk == 100.0  # 1000 units × 10 pips × 0.01
        """
        pip_size = self.pair_manager.get_pip_size(pair)
        return position_size * stop_pips * pip_size


class TrailingStopManager:
    """
    Manage trailing stop loss.
    
    Logic:
    1. Position enters at price P with initial stop S
    2. If profit reaches trigger_pips, activate trailing stop
    3. Trail stop follows price at trail_distance_pips below highest price
    4. Exit if price falls to trail stop level
    
    Parameters:
        - trigger_pips: 4 (activate after 4 pips profit)
        - trail_distance_pips: 3 (trail 3 pips behind peak)
    
    Examples:
        >>> trail_mgr = TrailingStopManager(pair_manager, trigger_pips=4, trail_distance_pips=3)
        >>> entry_price = 110.50
        >>> current_price = 110.54
        >>> stop_price = trail_mgr.update_stop(entry_price, current_price, 'USDJPY', initial_stop_pips=10)
    """
    
    def __init__(
        self,
        pair_manager: FXPairManager,
        trigger_pips: float = 4.0,
        trail_distance_pips: float = 3.0
    ):
        """
        Initialize trailing stop manager.
        
        Args:
            pair_manager: FXPairManager instance
            trigger_pips: Profit to activate trail (default 4 pips)
            trail_distance_pips: Distance to trail behind peak (default 3 pips)
        """
        self.pair_manager = pair_manager
        self.trigger_pips = trigger_pips
        self.trail_distance_pips = trail_distance_pips
        
        # State tracking (reset for each trade)
        self.is_active: Dict[str, bool] = {}
        self.highest_price: Dict[str, float] = {}
        self.lowest_price: Dict[str, float] = {}
    
    def reset_trade(self, trade_id: str):
        """Reset state for a new trade."""
        self.is_active[trade_id] = False
        self.highest_price[trade_id] = -np.inf
        self.lowest_price[trade_id] = np.inf
    
    def update_stop(
        self,
        entry_price: float,
        current_price: float,
        pair: str,
        direction: int,
        initial_stop_pips: float,
        trade_id: str = "default"
    ) -> float:
        """
        Update trailing stop for a position.
        
        Args:
            entry_price: Entry price
            current_price: Current market price
            pair: FX pair name
            direction: 1 for long, -1 for short
            initial_stop_pips: Initial stop distance in pips
            trade_id: Unique trade identifier
            
        Returns:
            Current stop price
            
        Examples:
            >>> # Long trade: entry 110.50, current 110.54
            >>> stop = trail_mgr.update_stop(110.50, 110.54, 'USDJPY', 1, 10)
            >>> # After 4 pips profit, trail activates at 110.51 (3 pips behind 110.54)
        """
        # Initialize trade state if needed
        if trade_id not in self.is_active:
            self.reset_trade(trade_id)
        
        # Calculate profit in pips
        price_move = (current_price - entry_price) * direction
        profit_pips = self.pair_manager.price_to_pips(price_move, pair)
        
        # Update highest/lowest price
        if direction == 1:  # Long
            self.highest_price[trade_id] = max(
                self.highest_price.get(trade_id, -np.inf),
                current_price
            )
        else:  # Short
            self.lowest_price[trade_id] = min(
                self.lowest_price.get(trade_id, np.inf),
                current_price
            )
        
        # Check if trail should activate
        if not self.is_active[trade_id] and profit_pips >= self.trigger_pips:
            self.is_active[trade_id] = True
        
        # Calculate stop price
        if self.is_active[trade_id]:
            # Trailing stop
            if direction == 1:  # Long
                stop_price = self.highest_price[trade_id] - \
                    self.pair_manager.pips_to_price(self.trail_distance_pips, pair)
            else:  # Short
                stop_price = self.lowest_price[trade_id] + \
                    self.pair_manager.pips_to_price(self.trail_distance_pips, pair)
        else:
            # Fixed initial stop
            if direction == 1:  # Long
                stop_price = entry_price - \
                    self.pair_manager.pips_to_price(initial_stop_pips, pair)
            else:  # Short
                stop_price = entry_price + \
                    self.pair_manager.pips_to_price(initial_stop_pips, pair)
        
        return stop_price
    
    def is_triggered(
        self,
        entry_price: float,
        current_price: float,
        pair: str,
        direction: int,
        initial_stop_pips: float,
        trade_id: str = "default"
    ) -> bool:
        """
        Check if stop has been triggered.
        
        Args:
            entry_price: Entry price
            current_price: Current market price
            pair: FX pair name
            direction: 1 for long, -1 for short
            initial_stop_pips: Initial stop distance in pips
            trade_id: Unique trade identifier
            
        Returns:
            True if stop triggered, False otherwise
        """
        stop_price = self.update_stop(
            entry_price, current_price, pair, direction, initial_stop_pips, trade_id
        )
        
        if direction == 1:  # Long
            return current_price <= stop_price
        else:  # Short
            return current_price >= stop_price


class TimeExitManager:
    """
    Manage time-based exits (max hold period).
    
    Logic: Exit position if held for > max_bars, regardless of P&L.
    
    Rationale: Mean reversion should complete quickly (1-3 bars).
    If not, signal was likely wrong → exit to free capital.
    
    Default: 5 bars max hold
    
    Examples:
        >>> time_mgr = TimeExitManager(max_bars=5)
        >>> should_exit = time_mgr.check_exit(entry_bar=0, current_bar=5)
        >>> assert should_exit is True
    """
    
    def __init__(self, max_bars: int = 5):
        """
        Initialize time exit manager.
        
        Args:
            max_bars: Maximum bars to hold position (default 5)
        """
        self.max_bars = max_bars
    
    def check_exit(self, entry_bar: int, current_bar: int) -> bool:
        """
        Check if max hold period reached.
        
        Args:
            entry_bar: Bar index at entry
            current_bar: Current bar index
            
        Returns:
            True if should exit, False otherwise
            
        Examples:
            >>> mgr = TimeExitManager(max_bars=5)
            >>> mgr.check_exit(0, 4)  # 4 bars held
            False
            >>> mgr.check_exit(0, 5)  # 5 bars held
            True
        """
        bars_held = current_bar - entry_bar
        return bars_held >= self.max_bars
    
    def bars_until_exit(self, entry_bar: int, current_bar: int) -> int:
        """
        Calculate bars remaining until forced exit.
        
        Args:
            entry_bar: Bar index at entry
            current_bar: Current bar index
            
        Returns:
            Bars remaining (0 if already at/past max)
        """
        bars_held = current_bar - entry_bar
        remaining = self.max_bars - bars_held
        return max(0, remaining)


# Utility functions

def calculate_profit_pips(
    entry_price: float,
    exit_price: float,
    direction: int,
    pair: str,
    pair_manager: FXPairManager
) -> float:
    """
    Calculate profit/loss in pips.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        direction: 1 for long, -1 for short
        pair: FX pair name
        pair_manager: FXPairManager instance
        
    Returns:
        Profit in pips (negative if loss)
        
    Examples:
        >>> manager = FXPairManager()
        >>> profit = calculate_profit_pips(110.50, 110.60, 1, 'USDJPY', manager)
        >>> assert profit == 10.0  # 10 pip profit
    """
    price_move = (exit_price - entry_price) * direction
    return pair_manager.price_to_pips(price_move, pair)


def calculate_profit_dollars(
    entry_price: float,
    exit_price: float,
    direction: int,
    position_size: float,
    pair: str,
    pair_manager: FXPairManager
) -> float:
    """
    Calculate profit/loss in dollars.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        direction: 1 for long, -1 for short
        position_size: Position size in units
        pair: FX pair name
        pair_manager: FXPairManager instance
        
    Returns:
        Profit in dollars (negative if loss)
    """
    profit_pips = calculate_profit_pips(
        entry_price, exit_price, direction, pair, pair_manager
    )
    pip_size = pair_manager.get_pip_size(pair)
    return position_size * profit_pips * pip_size
