"""
Comprehensive feature engineering library for FX data.

Provides feature generation with proper lag handling, z-score normalization,
technical indicators, and stationarity testing.
"""

from typing import List, Dict, Optional

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, kpss


class FeatureEngineering:
    """
    Feature engineering for FX quantitative research.
    
    All features use only lagged data (no lookahead bias).
    NaN rows are preserved with min_periods in rolling calculations.
    
    Examples:
        >>> fe = FeatureEngineering()
        >>> df = fe.add_momentum(df, windows=[5, 10, 20])
        >>> df = fe.add_volatility_features(df)
        >>> df = fe.add_zscore(df, 'returns', window=60)
    """
    
    def __init__(self):
        """Initialize feature engineering."""
        pass
    
    def add_momentum(
        self,
        df: pd.DataFrame,
        windows: List[int] = [5, 10, 20]
    ) -> pd.DataFrame:
        """
        Add momentum features (N-period returns).
        
        Args:
            df: DataFrame with 'close' prices
            windows: List of lookback windows
            
        Returns:
            DataFrame with momentum columns added
            
        Examples:
            >>> df = fe.add_momentum(df, windows=[5, 10, 20])
            >>> print(df[['close', 'momentum_5', 'momentum_20']].tail())
        """
        df = df.copy()
        
        for window in windows:
            df[f'momentum_{window}'] = df['close'] / df['close'].shift(window) - 1
        
        return df
    
    def add_volatility_features(
        self,
        df: pd.DataFrame,
        windows: List[int] = [10, 20, 60],
        annualize: int = 252
    ) -> pd.DataFrame:
        """
        Add volatility features with rolling and EWM variants.
        
        Args:
            df: DataFrame with price data
            windows: List of lookback windows
            annualize: Annualization factor
            
        Returns:
            DataFrame with volatility columns added
            
        Examples:
            >>> df = fe.add_volatility_features(df, windows=[10, 20])
            >>> print(df['volatility_20'].tail())
        """
        df = df.copy()
        
        # Calculate returns if not present
        if 'returns' not in df.columns:
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        for window in windows:
            # Rolling standard deviation
            df[f'volatility_{window}'] = (
                df['returns'].rolling(window=window, min_periods=max(1, window // 2)).std()
                * np.sqrt(annualize)
            )
            
            # Exponentially weighted moving average
            df[f'volatility_ewm_{window}'] = (
                df['returns'].ewm(span=window, min_periods=max(1, window // 2)).std()
                * np.sqrt(annualize)
            )
        
        return df
    
    def add_zscore(
        self,
        df: pd.DataFrame,
        column: str,
        window: int = 60,
        name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Add z-score normalized feature.
        
        Args:
            df: DataFrame
            column: Column to normalize
            window: Rolling window for mean/std calculation
            name: Optional name for new column (default: {column}_zscore)
            
        Returns:
            DataFrame with z-score column added
            
        Examples:
            >>> df = fe.add_zscore(df, 'returns', window=60)
            >>> print(df['returns_zscore'].describe())
        """
        df = df.copy()
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame")
        
        series = df[column]
        rolling_mean = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
        rolling_std = series.rolling(window=window, min_periods=max(1, window // 2)).std()
        
        zscore_col = name if name else f'{column}_zscore'
        df[zscore_col] = (series - rolling_mean) / rolling_std
        
        return df
    
    def add_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Add Relative Strength Index (RSI) indicator.
        
        Args:
            df: DataFrame with 'close' prices
            period: RSI period
            
        Returns:
            DataFrame with RSI column added
            
        Examples:
            >>> df = fe.add_rsi(df, period=14)
            >>> print(df['rsi'].tail())
        """
        df = df.copy()
        
        # Calculate price changes
        delta = df['close'].diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)
        
        # Calculate exponential moving averages
        avg_gains = gains.ewm(span=period, min_periods=period).mean()
        avg_losses = losses.ewm(span=period, min_periods=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def add_rolling_moments(
        self,
        df: pd.DataFrame,
        window: int = 60
    ) -> pd.DataFrame:
        """
        Add rolling skewness and kurtosis.
        
        Args:
            df: DataFrame with returns
            window: Rolling window size
            
        Returns:
            DataFrame with moment columns added
            
        Examples:
            >>> df = fe.add_rolling_moments(df, window=60)
            >>> print(df[['skewness', 'kurtosis']].tail())
        """
        df = df.copy()
        
        # Calculate returns if not present
        if 'returns' not in df.columns:
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Rolling skewness
        df['skewness'] = (
            df['returns'].rolling(window=window, min_periods=max(1, window // 2))
            .apply(lambda x: stats.skew(x.dropna()), raw=False)
        )
        
        # Rolling kurtosis
        df['kurtosis'] = (
            df['returns'].rolling(window=window, min_periods=max(1, window // 2))
            .apply(lambda x: stats.kurtosis(x.dropna()), raw=False)
        )
        
        return df
    
    def add_volatility_adjusted_returns(
        self,
        df: pd.DataFrame,
        vol_window: int = 20
    ) -> pd.DataFrame:
        """
        Add volatility-adjusted returns (returns / volatility).
        
        Useful for comparing returns across different volatility regimes.
        
        Args:
            df: DataFrame with returns
            vol_window: Window for volatility calculation
            
        Returns:
            DataFrame with vol-adjusted returns column added
            
        Examples:
            >>> df = fe.add_volatility_adjusted_returns(df, vol_window=20)
            >>> print(df['returns_vol_adj'].tail())
        """
        df = df.copy()
        
        # Calculate returns if not present
        if 'returns' not in df.columns:
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Calculate volatility
        vol = df['returns'].rolling(window=vol_window, min_periods=max(1, vol_window // 2)).std()
        
        # Volatility-adjusted returns
        df['returns_vol_adj'] = df['returns'] / vol
        
        return df
    
    def add_range_features(
        self,
        df: pd.DataFrame,
        windows: List[int] = [10, 20, 50]
    ) -> pd.DataFrame:
        """
        Add range-based microstructure features for exhaustion detection.
        
        Features:
        - bar_range: High - Low (raw price movement)
        - range_pct: Range as percentage of close price
        - median_range_N: Median range over N periods (normalization baseline)
        - range_expansion_N: Current range / median range (exhaustion signal)
        
        Hypothesis: Large range expansion (>0.8× median) signals exhaustion,
        especially when followed by failure to continue.
        
        Expected stationarity: range_pct and range_expansion should be stationary
        (normalized by price level).
        
        Args:
            df: DataFrame with OHLC data
            windows: Lookback windows for median calculation
            
        Returns:
            DataFrame with range features added
            
        Examples:
            >>> df = fe.add_range_features(df, windows=[20])
            >>> exhaustion = df['range_expansion_20'] > 0.8
            >>> print(f"Exhaustion bars: {exhaustion.sum()}")
        """
        df = df.copy()
        
        # Basic range
        df['bar_range'] = df['high'] - df['low']
        df['range_pct'] = df['bar_range'] / df['close']
        
        # Range expansion ratios for each window
        for window in windows:
            median_range = df['bar_range'].rolling(
                window=window, 
                min_periods=max(1, window // 2)
            ).median()
            df[f'median_range_{window}'] = median_range
            df[f'range_expansion_{window}'] = df['bar_range'] / median_range
        
        return df
    
    def add_close_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add close position within the bar's range.
        
        Feature: close_position = (close - low) / (high - low)
        - 1.0 = close at high (bullish)
        - 0.5 = close at midpoint (neutral)
        - 0.0 = close at low (bearish)
        
        Hypothesis: Closes in extreme zones (>0.65 or <0.35) combined with
        range expansion signal directional exhaustion.
        
        Expected stationarity: Stationary (bounded 0-1, mean-reverting).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with close_position column added
            
        Examples:
            >>> df = fe.add_close_position(df)
            >>> bullish_extreme = df['close_position'] > 0.65
            >>> bearish_extreme = df['close_position'] < 0.35
        """
        df = df.copy()
        
        # Handle zero range bars (open = high = low = close)
        range_nonzero = (df['high'] - df['low']).replace(0, np.nan)
        df['close_position'] = (df['close'] - df['low']) / range_nonzero
        
        # For zero-range bars, set to 0.5 (neutral)
        df['close_position'] = df['close_position'].fillna(0.5)
        
        return df
    
    def add_consecutive_direction(
        self,
        df: pd.DataFrame,
        windows: List[int] = [2, 3]
    ) -> pd.DataFrame:
        """
        Add features detecting consecutive directional bars.
        
        Features:
        - bar_direction: 1 if close > open (bullish), 0 otherwise
        - consecutive_bulls_N: Count of bullish bars in last N periods
        - consecutive_bears_N: Count of bearish bars in last N periods
        
        Hypothesis: ≥2 consecutive directional bars combined with range
        expansion signals momentum exhaustion.
        
        Expected stationarity: Stationary (counts are bounded, mean-reverting).
        
        Args:
            df: DataFrame with OHLC data
            windows: Lookback windows for counting
            
        Returns:
            DataFrame with consecutive direction features added
            
        Examples:
            >>> df = fe.add_consecutive_direction(df, windows=[2])
            >>> strong_bulls = df['consecutive_bulls_2'] >= 2
            >>> print(f"Strong bullish sequences: {strong_bulls.sum()}")
        """
        df = df.copy()
        
        # Bar direction: 1 = bullish (close > open), 0 = bearish/neutral
        df['bar_direction'] = (df['close'] > df['open']).astype(int)
        
        # Count consecutive directional bars
        for window in windows:
            # Consecutive bullish bars
            df[f'consecutive_bulls_{window}'] = (
                df['bar_direction'].rolling(window=window, min_periods=1).sum()
            )
            
            # Consecutive bearish bars (inverse)
            df[f'consecutive_bears_{window}'] = (
                (1 - df['bar_direction']).rolling(window=window, min_periods=1).sum()
            )
        
        return df
    
    def add_range_breakout_features(
        self,
        df: pd.DataFrame,
        windows: List[int] = [10, 20, 50]
    ) -> pd.DataFrame:
        """
        Add range breakout detection features.
        
        Features:
        - range_high_N: Highest high over N periods
        - range_low_N: Lowest low over N periods
        - breakout_up_N: 1 if close breaks above N-period high
        - breakout_down_N: 1 if close breaks below N-period low
        
        Hypothesis: Breakouts that fail to continue (next bar closes back in
        range) signal mean reversion opportunities.
        
        Expected stationarity: Breakout flags are stationary (binary indicators).
        
        Args:
            df: DataFrame with OHLC data
            windows: Lookback windows for range calculation
            
        Returns:
            DataFrame with breakout features added
            
        Examples:
            >>> df = fe.add_range_breakout_features(df, windows=[20])
            >>> breakouts = df['breakout_up_20'] | df['breakout_down_20']
            >>> print(f"Range breakouts: {breakouts.sum()}")
        """
        df = df.copy()
        
        for window in windows:
            # Range high/low (use shift to avoid lookahead bias)
            df[f'range_high_{window}'] = (
                df['high'].shift(1).rolling(window=window, min_periods=1).max()
            )
            df[f'range_low_{window}'] = (
                df['low'].shift(1).rolling(window=window, min_periods=1).min()
            )
            
            # Breakout detection
            df[f'breakout_up_{window}'] = (
                (df['close'] > df[f'range_high_{window}']).astype(int)
            )
            df[f'breakout_down_{window}'] = (
                (df['close'] < df[f'range_low_{window}']).astype(int)
            )
        
        return df
    
    def add_all_features(
        self,
        df: pd.DataFrame,
        momentum_windows: List[int] = [5, 10, 20],
        vol_windows: List[int] = [10, 20, 60],
        zscore_window: int = 60,
        rsi_period: int = 14,
        moments_window: int = 60,
        include_microstructure: bool = True
    ) -> pd.DataFrame:
        """
        Add comprehensive feature set.
        
        Args:
            df: DataFrame with OHLC data
            momentum_windows: Windows for momentum calculation
            vol_windows: Windows for volatility calculation
            zscore_window: Window for z-score normalization
            rsi_period: Period for RSI
            moments_window: Window for rolling moments
            include_microstructure: Include range/exhaustion features
            
        Returns:
            DataFrame with all features added
            
        Examples:
            >>> df = fe.add_all_features(df)
            >>> print(df.columns.tolist())
        """
        df = df.copy()
        
        # Add returns first
        if 'returns' not in df.columns:
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Add all feature categories
        df = self.add_momentum(df, windows=momentum_windows)
        df = self.add_volatility_features(df, windows=vol_windows)
        df = self.add_zscore(df, 'returns', window=zscore_window)
        df = self.add_rsi(df, period=rsi_period)
        df = self.add_rolling_moments(df, window=moments_window)
        df = self.add_volatility_adjusted_returns(df)
        
        # Add microstructure features (for exhaustion hypothesis)
        if include_microstructure:
            df = self.add_range_features(df, windows=[10, 20, 50])
            df = self.add_close_position(df)
            df = self.add_consecutive_direction(df, windows=[2, 3])
            df = self.add_range_breakout_features(df, windows=[10, 20, 50])
        
        return df


def test_stationarity(
    series: pd.Series,
    method: str = 'both'
) -> Dict[str, any]:
    """
    Test stationarity of a time series.
    
    Uses both ADF (Augmented Dickey-Fuller) and KPSS tests.
    - ADF null hypothesis: series has unit root (non-stationary)
    - KPSS null hypothesis: series is stationary
    
    Args:
        series: Time series to test
        method: 'adf', 'kpss', or 'both'
        
    Returns:
        Dictionary with test statistics and interpretation
        
    Examples:
        >>> # Test on price levels (should be non-stationary)
        >>> result = test_stationarity(df['close'])
        >>> print(f"Is stationary: {result['is_stationary']}")
        
        >>> # Test on returns (should be stationary)
        >>> result = test_stationarity(df['returns'].dropna())
        >>> print(f"Is stationary: {result['is_stationary']}")
    """
    series_clean = series.dropna()
    
    if len(series_clean) < 10:
        raise ValueError("Need at least 10 non-NaN values for stationarity test")
    
    result = {}
    
    if method in ['adf', 'both']:
        # ADF test
        adf_result = adfuller(series_clean, autolag='AIC')
        result['adf_statistic'] = float(adf_result[0])
        result['adf_pvalue'] = float(adf_result[1])
        result['adf_critical_values'] = adf_result[4]
        result['is_stationary_adf'] = adf_result[1] < 0.05  # Reject null at 5%
    
    if method in ['kpss', 'both']:
        # KPSS test
        kpss_result = kpss(series_clean, regression='c', nlags='auto')
        result['kpss_statistic'] = float(kpss_result[0])
        result['kpss_pvalue'] = float(kpss_result[1])
        result['kpss_critical_values'] = kpss_result[3]
        result['is_stationary_kpss'] = kpss_result[1] > 0.05  # Accept null at 5%
    
    # Overall assessment
    if method == 'both':
        result['is_stationary'] = (
            result.get('is_stationary_adf', False) and
            result.get('is_stationary_kpss', False)
        )
    elif method == 'adf':
        result['is_stationary'] = result.get('is_stationary_adf', False)
    else:
        result['is_stationary'] = result.get('is_stationary_kpss', False)
    
    return result


def make_stationary(
    series: pd.Series,
    method: str = 'diff'
) -> pd.Series:
    """
    Transform series to make it stationary.
    
    Args:
        series: Time series to transform
        method: 'diff' for differencing, 'log_diff' for log differencing
        
    Returns:
        Stationary time series
        
    Examples:
        >>> # Make price series stationary
        >>> stationary_prices = make_stationary(df['close'], method='log_diff')
        >>> result = test_stationarity(stationary_prices.dropna())
        >>> assert result['is_stationary']
    """
    if method == 'diff':
        return series.diff()
    elif method == 'log_diff':
        return np.log(series / series.shift(1))
    else:
        raise ValueError(f"Unknown method: {method}. Use 'diff' or 'log_diff'")
