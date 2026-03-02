"""
Transaction cost models for FX trading.

Implements realistic cost models including spread, slippage, market impact,
and swap costs with configurable parameters.
"""

from typing import Protocol, Dict, Optional, Literal
from datetime import datetime

import numpy as np
import pandas as pd


class TransactionCostModel(Protocol):
    """Protocol for transaction cost models."""
    
    def calculate_cost(
        self,
        price: float,
        size: float,
        side: Literal['buy', 'sell'],
        timestamp: pd.Timestamp,
        **context
    ) -> float:
        """Calculate transaction cost for a trade."""
        ...


class FXCostModel:
    """
    Comprehensive FX transaction cost model.
    
    Implements:
    - Spread costs (configurable by pair tier)
    - Slippage (square-root model)
    - Market impact (power law)
    - Swap/rollover costs (optional)
    
    Examples:
        >>> cost_model = FXCostModel(
        ...     spread_bps_major=1.5,
        ...     slippage_coef=0.1,
        ...     impact_exponent=0.5
        ... )
        >>> cost = cost_model.total_cost(
        ...     price=1.1000,
        ...     size=100000,
        ...     side='buy',
        ...     pair_tier='major',
        ...     volume=1e6
        ... )
    """
    
    def __init__(
        self,
        spread_bps_major: float = 1.5,
        spread_bps_minor: float = 3.0,
        spread_bps_exotic: float = 10.0,
        slippage_coefficient: float = 0.1,
        market_impact_exponent: float = 0.5,
        market_impact_coefficient: float = 0.05,
        enable_swap_costs: bool = True,
        swap_rates_df: Optional[pd.DataFrame] = None
    ):
        """
        Initialize FX cost model.
        
        Args:
            spread_bps_major: Spread for major pairs (basis points)
            spread_bps_minor: Spread for minor pairs (basis points)
            spread_bps_exotic: Spread for exotic pairs (basis points)
            slippage_coefficient: Slippage model coefficient
            market_impact_exponent: Market impact exponent (~0.5 for sqrt model)
            market_impact_coefficient: Market impact coefficient
            enable_swap_costs: Whether to apply swap costs
            swap_rates_df: DataFrame with swap rate data (optional)
        """
        self.spread_bps = {
            'major': spread_bps_major,
            'minor': spread_bps_minor,
            'exotic': spread_bps_exotic
        }
        self.slippage_coefficient = slippage_coefficient
        self.market_impact_exponent = market_impact_exponent
        self.market_impact_coefficient = market_impact_coefficient
        self.enable_swap_costs = enable_swap_costs
        self.swap_rates_df = swap_rates_df
    
    def calculate_spread_cost(
        self,
        price: float,
        size: float,
        spread_bps: float
    ) -> float:
        """
        Calculate spread cost.
        
        Formula: 0.5 * (spread_bps / 10000) * price * |size|
        
        Args:
            price: Execution price
            size: Trade size (signed, negative for sell)
            spread_bps: Spread in basis points
            
        Returns:
            Spread cost (always positive)
            
        Examples:
            >>> cost = cost_model.calculate_spread_cost(1.1000, 100000, 1.5)
            >>> print(f"Spread cost: ${cost:.2f}")
        """
        return 0.5 * (spread_bps / 10000) * price * abs(size)
    
    def calculate_slippage(
        self,
        price: float,
        size: float,
        volume: float,
        volatility: float = 0.01
    ) -> float:
        """
        Calculate slippage cost using square-root model.
        
        Formula: volatility * sqrt(|size| / volume) * price * coefficient
        
        Args:
            price: Execution price
            size: Trade size (signed)
            volume: Average daily volume
            volatility: Current volatility estimate
            
        Returns:
            Slippage cost (always positive)
            
        Examples:
            >>> cost = cost_model.calculate_slippage(1.1000, 100000, 1e6, 0.01)
            >>> print(f"Slippage: ${cost:.2f}")
        """
        if volume <= 0:
            return 0.0
        
        slippage = (
            volatility *
            np.sqrt(abs(size) / volume) *
            price *
            self.slippage_coefficient
        )
        
        return abs(slippage)
    
    def calculate_market_impact(
        self,
        size: float,
        daily_volume: float,
        price: float
    ) -> float:
        """
        Calculate market impact using power law model.
        
        Formula: price * (|size| / daily_volume) ^ exponent * coefficient
        
        Args:
            size: Trade size (signed)
            daily_volume: Average daily volume
            price: Execution price
            
        Returns:
            Market impact cost (always positive)
            
        Examples:
            >>> impact = cost_model.calculate_market_impact(100000, 1e6, 1.1000)
            >>> print(f"Market impact: ${impact:.2f}")
        """
        if daily_volume <= 0:
            return 0.0
        
        impact = (
            price *
            (abs(size) / daily_volume) ** self.market_impact_exponent *
            self.market_impact_coefficient
        )
        
        return abs(impact)
    
    def calculate_swap_cost(
        self,
        position: float,
        pair: str,
        timestamp: pd.Timestamp
    ) -> float:
        """
        Calculate swap/rollover cost.
        
        Applied at 5 PM EST daily, triple on Wednesday (covers weekend).
        
        Args:
            position: Position size (positive for long, negative for short)
            pair: Currency pair (e.g., 'EURUSD')
            timestamp: Timestamp for swap calculation
            
        Returns:
            Swap cost (can be positive or negative)
            
        Examples:
            >>> swap = cost_model.calculate_swap_cost(100000, 'EURUSD', pd.Timestamp.now())
            >>> print(f"Swap cost: ${swap:.2f}")
        """
        if not self.enable_swap_costs or self.swap_rates_df is None:
            return 0.0
        
        # Check if swap rate data available for this pair and time
        if pair not in self.swap_rates_df.columns:
            return 0.0
        
        try:
            # Get swap rate (annualized interest differential)
            swap_rate = self.swap_rates_df.loc[timestamp, pair]
        except (KeyError, IndexError):
            # If exact timestamp not found, use nearest available
            nearest_idx = self.swap_rates_df.index.get_indexer([timestamp], method='nearest')[0]
            if nearest_idx >= 0 and nearest_idx < len(self.swap_rates_df):
                swap_rate = self.swap_rates_df.iloc[nearest_idx][pair]
            else:
                return 0.0
        
        # Calculate daily swap
        daily_swap = (swap_rate / 360) * position
        
        # Triple swap on Wednesday (covers weekend)
        if timestamp.dayofweek == 2:  # Wednesday = 2
            daily_swap *= 3
        
        return daily_swap
    
    def total_cost(
        self,
        price: float,
        size: float,
        side: Literal['buy', 'sell'],
        pair_tier: str = 'major',
        volume: Optional[float] = None,
        volatility: float = 0.01,
        timestamp: Optional[pd.Timestamp] = None,
        pair: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate total transaction cost with breakdown.
        
        Args:
            price: Execution price
            size: Trade size (unsigned)
            side: 'buy' or 'sell'
            pair_tier: 'major', 'minor', or 'exotic'
            volume: Average daily volume (for slippage/impact)
            volatility: Current volatility estimate
            timestamp: Timestamp for swap cost
            pair: Currency pair name for swap cost
            
        Returns:
            Dictionary with cost breakdown
            
        Examples:
            >>> costs = cost_model.total_cost(
            ...     price=1.1000,
            ...     size=100000,
            ...     side='buy',
            ...     pair_tier='major',
            ...     volume=1e6,
            ...     volatility=0.01
            ... )
            >>> print(f"Total cost: ${costs['total']:.2f}")
        """
        # Convert side to signed size
        signed_size = size if side == 'buy' else -size
        
        # Get spread for pair tier
        spread_bps = self.spread_bps.get(pair_tier, self.spread_bps['major'])
        
        # Calculate component costs
        spread_cost = self.calculate_spread_cost(price, signed_size, spread_bps)
        
        slippage_cost = 0.0
        if volume is not None and volume > 0:
            slippage_cost = self.calculate_slippage(price, signed_size, volume, volatility)
        
        impact_cost = 0.0
        if volume is not None and volume > 0:
            impact_cost = self.calculate_market_impact(signed_size, volume, price)
        
        swap_cost = 0.0
        if timestamp is not None and pair is not None:
            swap_cost = self.calculate_swap_cost(signed_size, pair, timestamp)
        
        # Total cost (swap can be negative/positive, others always positive)
        total = spread_cost + slippage_cost + impact_cost + swap_cost
        
        return {
            'spread': spread_cost,
            'slippage': slippage_cost,
            'impact': impact_cost,
            'swap': swap_cost,
            'total': total,
            'bps': (total / (price * abs(signed_size))) * 10000 if abs(signed_size) > 0 else 0.0
        }
