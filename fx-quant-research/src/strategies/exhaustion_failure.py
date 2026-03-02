"""
Exhaustion-Failure-to-Continue Strategy

Implements the mean reversion hypothesis:
When a market shows extreme directional movement (exhaustion) but then fails
to continue that movement, it signals a high-probability mean reversion opportunity.

Three-part pattern:
1. EXHAUSTION: Range expansion + extreme close + consecutive direction
2. FAILURE: Next bar closes back inside prior range
3. MEAN REVERSION: Counter-trend entry with tight stops

References:
    User hypothesis specification (March 2, 2026)
    Expected: >70% win rate, ~40 high-quality signals on NZDJPY
"""

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yaml


class ExhaustionFailureStrategy:
    """
    Exhaustion-Failure-to-Continue mean reversion strategy.
    
    Logic:
    1. Detect range expansion (>0.8× median range over 20 bars)
    2. Confirm directional pressure (≥2 consecutive bars, close in extreme zone)
    3. Wait for failure-to-continue (next bar closes back inside prior range)
    4. Enter counter-trend position
    
    Signal values:
        1: Long (bearish exhaustion failed → revert up)
        0: Flat (no signal)
       -1: Short (bullish exhaustion failed → revert down)
    
    Examples:
        >>> strategy = ExhaustionFailureStrategy()
        >>> signals = strategy.generate_signals(df, config)
        >>> trades = (signals != 0).sum()
        >>> print(f"Generated {trades} trade signals")
    """
    
    def __init__(
        self,
        range_expansion_threshold: float = 0.8,
        median_range_window: int = 20,
        extreme_zone_upper: float = 0.65,
        extreme_zone_lower: float = 0.35,
        consecutive_bars_required: int = 2,
        enable_failure_filter: bool = True
    ):
        """
        Initialize strategy with parameters.
        
        Args:
            range_expansion_threshold: Range > threshold × median (default 0.8)
            median_range_window: Window for median range calculation (default 20)
            extreme_zone_upper: Top percentile for bullish extreme (default 0.65 = top 35%)
            extreme_zone_lower: Bottom percentile for bearish extreme (default 0.35 = bottom 35%)
            consecutive_bars_required: Minimum consecutive directional bars (default 2)
            enable_failure_filter: Apply failure-to-continue filter (default True)
        """
        self.range_expansion_threshold = range_expansion_threshold
        self.median_range_window = median_range_window
        self.extreme_zone_upper = extreme_zone_upper
        self.extreme_zone_lower = extreme_zone_lower
        self.consecutive_bars_required = consecutive_bars_required
        self.enable_failure_filter = enable_failure_filter
    
    @classmethod
    def from_config(cls, config_path: str = "config/config.yaml") -> "ExhaustionFailureStrategy":
        """
        Create strategy from YAML configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configured strategy instance
            
        Examples:
            >>> strategy = ExhaustionFailureStrategy.from_config()
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        params = config.get('exhaustion_strategy', {})
        
        return cls(
            range_expansion_threshold=params.get('range_expansion_threshold', 0.8),
            median_range_window=params.get('median_range_window', 20),
            extreme_zone_upper=params.get('extreme_zone_upper', 0.65),
            extreme_zone_lower=params.get('extreme_zone_lower', 0.35),
            consecutive_bars_required=params.get('consecutive_bars_required', 2),
            enable_failure_filter=params.get('enable_failure_filter', True)
        )
    
    def detect_exhaustion(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Detect bullish and bearish exhaustion.
        
        Conditions (all must be met):
        1. Range expansion: (high - low) > threshold × median_range
        2. Directional pressure: ≥N consecutive bars in same direction
        3. Extreme close: Close in top 35% (bullish) or bottom 35% (bearish)
        
        Args:
            df: DataFrame with OHLC and derived features
            
        Returns:
            Tuple of (bullish_exhaustion, bearish_exhaustion) boolean Series
            
        Examples:
            >>> bulls, bears = strategy.detect_exhaustion(df)
            >>> print(f"Bullish exhaustion bars: {bulls.sum()}")
        """
        # Condition 1: Range expansion
        bar_range = df['high'] - df['low']
        median_range = bar_range.rolling(
            window=self.median_range_window,
            min_periods=max(1, self.median_range_window // 2)
        ).median()
        range_expansion = bar_range / median_range
        is_expanded = range_expansion > self.range_expansion_threshold
        
        # Condition 2: Close position within bar
        range_nonzero = (df['high'] - df['low']).replace(0, np.nan)
        close_position = (df['close'] - df['low']) / range_nonzero
        close_position = close_position.fillna(0.5)  # Neutral for zero-range bars
        
        # Condition 3: Directional pressure (consecutive bars)
        bar_direction = (df['close'] > df['open']).astype(int)
        consecutive_bulls = bar_direction.rolling(
            window=self.consecutive_bars_required,
            min_periods=self.consecutive_bars_required
        ).sum()
        consecutive_bears = (1 - bar_direction).rolling(
            window=self.consecutive_bars_required,
            min_periods=self.consecutive_bars_required
        ).sum()
        
        # Bullish exhaustion: Expanded range + consecutive bulls + close near high
        bullish_exhaustion = (
            is_expanded &
            (consecutive_bulls >= self.consecutive_bars_required) &
            (close_position > self.extreme_zone_upper)
        )
        
        # Bearish exhaustion: Expanded range + consecutive bears + close near low
        bearish_exhaustion = (
            is_expanded &
            (consecutive_bears >= self.consecutive_bars_required) &
            (close_position < self.extreme_zone_lower)
        )
        
        return bullish_exhaustion, bearish_exhaustion
    
    def detect_failure_to_continue(
        self,
        df: pd.DataFrame,
        bullish_exhaustion: pd.Series,
        bearish_exhaustion: pd.Series
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Detect failure-to-continue after exhaustion.
        
        Failure conditions:
        - After bullish exhaustion: Next bar closes back inside prior range
          (close[t+1] < high[t])
        - After bearish exhaustion: Next bar closes back inside prior range
          (close[t+1] > low[t])
        
        This is the critical filter: reduces ~158 exhaustion signals → ~40 trades
        
        Args:
            df: DataFrame with OHLC data
            bullish_exhaustion: Boolean Series indicating bullish exhaustion
            bearish_exhaustion: Boolean Series indicating bearish exhaustion
            
        Returns:
            Tuple of (short_signal, long_signal) boolean Series
            
        Examples:
            >>> short, long = strategy.detect_failure_to_continue(df, bulls, bears)
            >>> print(f"Short signals: {short.sum()}, Long signals: {long.sum()}")
        """
        if not self.enable_failure_filter:
            # No filter: signal immediately on exhaustion
            return bullish_exhaustion, bearish_exhaustion
        
        # Failure detection: CURRENT bar closes back inside PRIOR bar's range
        # This avoids look-ahead bias by using only known information
        
        # Shift exhaustion forward: exhaustion_prev[t] = exhaustion[t-1]
        bullish_exhaustion_prev = bullish_exhaustion.shift(1).fillna(False)
        bearish_exhaustion_prev = bearish_exhaustion.shift(1).fillna(False)
        
        # Get prior bar's high/low
        prior_high = df['high'].shift(1)
        prior_low = df['low'].shift(1)
        current_close = df['close']
        
        # After bullish exhaustion at t-1, if current bar closes below prior high → failure
        bullish_failure = bullish_exhaustion_prev & (current_close < prior_high)
        
        # After bearish exhaustion at t-1, if current bar closes above prior low → failure  
        bearish_failure = bearish_exhaustion_prev & (current_close > prior_low)
        
        return bullish_failure, bearish_failure
    
    def generate_signals(
        self,
        df: pd.DataFrame,
        regime: Optional[pd.Series] = None,
        target_regime: Optional[int] = None
    ) -> pd.Series:
        """
        Generate trading signals (-1, 0, 1).
        
        Signal logic:
        - After bullish exhaustion fails → SHORT (-1): expect mean reversion down
        - After bearish exhaustion fails → LONG (1): expect mean reversion up
        - Otherwise → FLAT (0): no position
        
        Optional regime filter: Only trade in specified regime state.
        
        Args:
            df: DataFrame with OHLC data (must contain required columns)
            regime: Optional Series with regime states (0, 1, 2)
            target_regime: Optional target regime to filter signals
            
        Returns:
            Series with signals (-1, 0, 1) aligned with df.index
            
        Raises:
            ValueError: If required columns missing from df
            
        Examples:
            >>> signals = strategy.generate_signals(df)
            >>> print(f"Long: {(signals == 1).sum()}, Short: {(signals == -1).sum()}")
        """
        # Validate required columns
        required_cols = ['open', 'high', 'low', 'close']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Step 1: Detect exhaustion
        bullish_exhaustion, bearish_exhaustion = self.detect_exhaustion(df)
        
        # Step 2: Detect failure-to-continue
        bullish_failure, bearish_failure = self.detect_failure_to_continue(
            df, bullish_exhaustion, bearish_exhaustion
        )
        
        # Step 3: Generate signals
        # Bullish failure → SHORT (exhaustion up failed, revert down)
        # Bearish failure → LONG (exhaustion down failed, revert up)
        signals = pd.Series(0, index=df.index, dtype=int)
        signals[bullish_failure] = -1  # Short
        signals[bearish_failure] = 1   # Long
        
        # Step 4: Apply optional regime filter
        if regime is not None and target_regime is not None:
            valid_regime = (regime == target_regime)
            signals = signals * valid_regime.astype(int)
        
        return signals
    
    def get_signal_diagnostics(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Get diagnostic information about signal generation.
        
        Useful for understanding how the failure filter impacts signal count.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with signal counts:
                - bullish_exhaustion: Count of bullish exhaustion bars
                - bearish_exhaustion: Count of bearish exhaustion bars
                - total_exhaustion: Total exhaustion bars
                - bullish_failure: Count after failure filter
                - bearish_failure: Count after failure filter
                - total_signals: Total tradeable signals
                - reduction_ratio: Ratio of signals to exhaustion bars
            
        Examples:
            >>> diagnostics = strategy.get_signal_diagnostics(df)
            >>> print(f"Exhaustion bars: {diagnostics['total_exhaustion']}")
            >>> print(f"Tradeable signals: {diagnostics['total_signals']}")
            >>> print(f"Reduction ratio: {diagnostics['reduction_ratio']:.2%}")
        """
        # Detect exhaustion
        bullish_exhaustion, bearish_exhaustion = self.detect_exhaustion(df)
        
        # Detect failures
        bullish_failure, bearish_failure = self.detect_failure_to_continue(
            df, bullish_exhaustion, bearish_exhaustion
        )
        
        total_exhaustion = bullish_exhaustion.sum() + bearish_exhaustion.sum()
        total_signals = bullish_failure.sum() + bearish_failure.sum()
        
        return {
            'bullish_exhaustion': int(bullish_exhaustion.sum()),
            'bearish_exhaustion': int(bearish_exhaustion.sum()),
            'total_exhaustion': int(total_exhaustion),
            'bullish_failure': int(bullish_failure.sum()),
            'bearish_failure': int(bearish_failure.sum()),
            'total_signals': int(total_signals),
            'reduction_ratio': float(total_signals / total_exhaustion) if total_exhaustion > 0 else 0.0
        }


def validate_strategy_setup(df: pd.DataFrame) -> bool:
    """
    Validate that DataFrame has required structure for strategy.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        True if valid, False otherwise (with warnings printed)
        
    Examples:
        >>> if validate_strategy_setup(df):
        ...     strategy = ExhaustionFailureStrategy()
        ...     signals = strategy.generate_signals(df)
    """
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing:
        print(f"❌ Missing required columns: {missing}")
        return False
    
    # Check OHLC logic
    invalid_ohlc = (
        (df['high'] < df['low']) |
        (df['high'] < df['open']) |
        (df['high'] < df['close']) |
        (df['low'] > df['open']) |
        (df['low'] > df['close'])
    )
    
    if invalid_ohlc.any():
        print(f"❌ Invalid OHLC data detected in {invalid_ohlc.sum()} bars")
        return False
    
    # Check for sufficient data
    min_bars = 50
    if len(df) < min_bars:
        print(f"❌ Insufficient data: {len(df)} bars (minimum {min_bars})")
        return False
    
    print(f"✅ Strategy setup validated: {len(df)} bars, all required columns present")
    return True
