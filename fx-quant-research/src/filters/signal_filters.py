"""
Signal Filtering Module

Days 22-24: Advanced filters to improve signal quality:
- Volatility regime (only trade high-vol periods)
- Time-of-day (avoid illiquid hours)
- Trend strength (ranging markets only)
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from datetime import time


class SignalFilter:
    """
    Apply filters to trading signals to improve quality.
    
    Filters:
    1. Volatility regime: Only trade when volatility is elevated
    2. Time-of-day: Avoid low liquidity hours
    3. Trend strength: Only trade in ranging (non-trending) markets
    """
    
    def __init__(
        self,
        vol_window: int = 20,
        vol_threshold_percentile: float = 50.0,
        liquid_hours_start: str = "08:00",
        liquid_hours_end: str = "17:00",
        trend_window: int = 20,
        trend_threshold: float = 0.3
    ):
        """
        Initialize signal filters.
        
        Args:
            vol_window: Window for volatility calculation
            vol_threshold_percentile: Percentile threshold for high-vol regime
            liquid_hours_start: Start of liquid trading hours (UTC)
            liquid_hours_end: End of liquid trading hours (UTC)
            trend_window: Window for trend strength calculation
            trend_threshold: Max normalized ADX for "ranging" market
        """
        self.vol_window = vol_window
        self.vol_threshold_percentile = vol_threshold_percentile
        self.liquid_hours_start = time.fromisoformat(liquid_hours_start)
        self.liquid_hours_end = time.fromisoformat(liquid_hours_end)
        self.trend_window = trend_window
        self.trend_threshold = trend_threshold
    
    def detect_volatility_regime(self, df: pd.DataFrame) -> pd.Series:
        """
        Identify high volatility periods.
        
        Uses realized volatility (std of returns) compared to rolling median.
        
        Args:
            df: DataFrame with 'close' or 'returns'
            
        Returns:
            Boolean Series indicating high-vol periods
        """
        if 'returns' not in df.columns:
            returns = df['close'].pct_change()
        else:
            returns = df['returns']
        
        # Calculate realized volatility
        realized_vol = returns.rolling(
            window=self.vol_window,
            min_periods=max(1, self.vol_window // 2)
        ).std()
        
        # Calculate rolling percentile threshold
        vol_threshold = realized_vol.rolling(
            window=100,
            min_periods=20
        ).quantile(self.vol_threshold_percentile / 100.0)
        
        # High volatility when current vol > threshold
        high_vol = realized_vol > vol_threshold
        
        return high_vol.fillna(False)
    
    def detect_liquid_hours(self, df: pd.DataFrame) -> pd.Series:
        """
        Identify liquid trading hours.
        
        Args:
            df: DataFrame with DatetimeIndex
            
        Returns:
            Boolean Series indicating liquid hours
        """
        # Extract hour from index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")
        
        hour = df.index.hour
        
        # Liquid hours: between start and end
        liquid = (hour >= self.liquid_hours_start.hour) & (hour < self.liquid_hours_end.hour)
        
        return liquid
    
    def detect_ranging_market(self, df: pd.DataFrame) -> pd.Series:
        """
        Identify ranging (non-trending) markets.
        
        Uses a simplified ADX-like measure based on directional movement.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Boolean Series indicating ranging market
        """
        # Calculate directional movement
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True range
        hl = high - low
        hc = abs(high - close.shift(1))
        lc = abs(low - close.shift(1))
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        
        # Directional movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        # Positive/negative directional indicators
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smoothed indicators
        plus_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(
            window=self.trend_window,
            min_periods=max(1, self.trend_window // 2)
        ).mean()
        
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(
            window=self.trend_window,
            min_periods=max(1, self.trend_window // 2)
        ).mean()
        
        tr_smooth = tr.rolling(
            window=self.trend_window,
            min_periods=max(1, self.trend_window // 2)
        ).mean()
        
        # Directional indicators
        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth
        
        # Simplified ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(
            window=self.trend_window,
            min_periods=max(1, self.trend_window // 2)
        ).mean()
        
        # Normalize ADX to 0-1 range (typically 0-100)
        adx_normalized = adx / 100.0
        
        # Ranging market when ADX is low (weak trend)
        ranging = adx_normalized < self.trend_threshold
        
        return ranging.fillna(False)
    
    def apply_filters(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        enable_vol_filter: bool = True,
        enable_time_filter: bool = True,
        enable_trend_filter: bool = True
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Apply all filters to signals.
        
        Args:
            df: DataFrame with OHLC data
            signals: Original signals (-1, 0, 1)
            enable_vol_filter: Apply volatility regime filter
            enable_time_filter: Apply time-of-day filter
            enable_trend_filter: Apply trend strength filter
            
        Returns:
            Tuple of (filtered_signals, filter_diagnostics)
        """
        # Calculate filters
        high_vol = self.detect_volatility_regime(df) if enable_vol_filter else pd.Series(True, index=df.index)
        liquid_hours = self.detect_liquid_hours(df) if enable_time_filter else pd.Series(True, index=df.index)
        ranging = self.detect_ranging_market(df) if enable_trend_filter else pd.Series(True, index=df.index)
        
        # Combine filters (all must be true)
        filter_pass = high_vol & liquid_hours & ranging
        
        # Apply to signals
        filtered_signals = signals * filter_pass.astype(int)
        
        # Diagnostics
        diagnostics = pd.DataFrame({
            'original_signal': signals != 0,
            'high_vol': high_vol,
            'liquid_hours': liquid_hours,
            'ranging': ranging,
            'filter_pass': filter_pass,
            'filtered_signal': filtered_signals != 0
        })
        
        return filtered_signals, diagnostics
    
    def get_filter_statistics(self, diagnostics: pd.DataFrame) -> dict:
        """
        Calculate statistics about filter impact.
        
        Args:
            diagnostics: DataFrame from apply_filters
            
        Returns:
            Dictionary of filter statistics
        """
        original_signals = diagnostics['original_signal'].sum()
        filtered_signals = diagnostics['filtered_signal'].sum()
        
        stats = {
            'original_signals': int(original_signals),
            'filtered_signals': int(filtered_signals),
            'reduction_ratio': (1 - filtered_signals / original_signals) if original_signals > 0 else 0.0,
            'high_vol_pass_rate': diagnostics['high_vol'].mean(),
            'liquid_hours_pass_rate': diagnostics['liquid_hours'].mean(),
            'ranging_pass_rate': diagnostics['ranging'].mean(),
            'all_filters_pass_rate': diagnostics['filter_pass'].mean(),
            'signals_rejected_by_vol': ((diagnostics['original_signal']) & (~diagnostics['high_vol'])).sum(),
            'signals_rejected_by_time': ((diagnostics['original_signal']) & (~diagnostics['liquid_hours'])).sum(),
            'signals_rejected_by_trend': ((diagnostics['original_signal']) & (~diagnostics['ranging'])).sum()
        }
        
        return stats


def demonstrate_filters():
    """Demonstrate filter usage with example."""
    
    # Create example data
    dates = pd.date_range('2025-01-01', periods=1000, freq='1H')
    np.random.seed(42)
    
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(1000) * 0.1),
        'high': 100 + np.cumsum(np.random.randn(1000) * 0.1) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(1000) * 0.1) - 0.5,
        'returns': np.random.randn(1000) * 0.01
    }, index=dates)
    
    # Create random signals
    signals = pd.Series(np.random.choice([-1, 0, 1], size=1000, p=[0.1, 0.8, 0.1]), index=dates)
    
    # Apply filters
    filter_engine = SignalFilter(
        vol_window=20,
        vol_threshold_percentile=60.0,  # Only top 40% volatility
        liquid_hours_start="08:00",
        liquid_hours_end="16:00",
        trend_window=20,
        trend_threshold=0.25  # Low ADX = ranging
    )
    
    filtered_signals, diagnostics = filter_engine.apply_filters(
        df, signals,
        enable_vol_filter=True,
        enable_time_filter=True,
        enable_trend_filter=True
    )
    
    # Statistics
    stats = filter_engine.get_filter_statistics(diagnostics)
    
    print("Filter Performance:")
    print(f"  Original signals: {stats['original_signals']}")
    print(f"  Filtered signals: {stats['filtered_signals']}")
    print(f"  Reduction: {stats['reduction_ratio']*100:.1f}%")
    print(f"\nFilter Pass Rates:")
    print(f"  High volatility: {stats['high_vol_pass_rate']*100:.1f}%")
    print(f"  Liquid hours: {stats['liquid_hours_pass_rate']*100:.1f}%")
    print(f"  Ranging market: {stats['ranging_pass_rate']*100:.1f}%")
    print(f"  All filters: {stats['all_filters_pass_rate']*100:.1f}%")
    print(f"\nSignals Rejected:")
    print(f"  By volatility: {stats['signals_rejected_by_vol']}")
    print(f"  By time: {stats['signals_rejected_by_time']}")
    print(f"  By trend: {stats['signals_rejected_by_trend']}")


if __name__ == "__main__":
    demonstrate_filters()
