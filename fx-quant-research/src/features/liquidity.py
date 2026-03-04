"""
Liquidity feature engineering for FX data.

Calculates spread-based features and effective liquidity scores
for position sizing and cost estimation.
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats


def calculate_spread_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate spread-based features if spread data is available.
    
    Args:
        df: DataFrame with 'spread' column and price data
        
    Returns:
        DataFrame with additional spread feature columns
        
    Raises:
        ValueError: If 'spread' column not found
        
    Examples:
        >>> df = calculate_spread_features(df)
        >>> print(df[['spread', 'spread_pct', 'spread_zscore']].tail())
    """
    if 'spread' not in df.columns:
        raise ValueError("DataFrame must contain 'spread' column")
    
    df = df.copy()
    
    # Calculate mid price
    if 'high' in df.columns and 'low' in df.columns:
        mid_price = (df['high'] + df['low']) / 2
    elif 'close' in df.columns:
        mid_price = df['close']
    else:
        raise ValueError("DataFrame must contain price columns")
    
    # Spread as percentage of price
    df['spread_pct'] = (df['spread'] / mid_price) * 100
    
    # Spread z-score (rolling 60-period)
    spread_mean = df['spread'].rolling(window=60, min_periods=20).mean()
    spread_std = df['spread'].rolling(window=60, min_periods=20).std()
    df['spread_zscore'] = (df['spread'] - spread_mean) / spread_std
    
    # Spread momentum (change over 5 periods)
    df['spread_momentum'] = df['spread'] / df['spread'].shift(5) - 1
    
    # Rolling spread percentile (relative to recent history)
    df['spread_percentile'] = (
        df['spread'].rolling(window=60, min_periods=20)
        .apply(lambda x: stats.percentileofscore(x, x.iloc[-1]) / 100, raw=False)
    )
    
    return df


def effective_liquidity_score(
    df: pd.DataFrame,
    volume_weight: float = 0.5,
    spread_weight: float = 0.5
) -> pd.Series:
    """
    Calculate effective liquidity score combining volume and spread.
    
    Higher score indicates better liquidity (high volume, low spread).
    Normalized to 0-1 range using rolling percentiles.
    
    Args:
        df: DataFrame with 'volume' and 'spread' columns
        volume_weight: Weight for volume component (0-1)
        spread_weight: Weight for spread component (0-1)
        
    Returns:
        Series with liquidity scores
        
    Examples:
        >>> liquidity = effective_liquidity_score(df)
        >>> print(f"Current liquidity: {liquidity.iloc[-1]:.2f}")
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    if 'spread' not in df.columns:
        raise ValueError("DataFrame must contain 'spread' column")
    
    # Normalize volume to 0-1 using rolling percentile rank
    volume_norm = (
        df['volume'].rolling(window=60, min_periods=20)
        .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    )
    
    # Normalize spread inversely (lower is better) to 0-1
    spread_norm = (
        df['spread'].rolling(window=60, min_periods=20)
        .apply(lambda x: 1 - pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    )
    
    # Weighted combination
    liquidity_score = (volume_weight * volume_norm + spread_weight * spread_norm)
    
    return liquidity_score


def calculate_volume_features(
    df: pd.DataFrame,
    windows: list = [5, 10, 20]
) -> pd.DataFrame:
    """
    Calculate volume-based features.
    
    Args:
        df: DataFrame with 'volume' column
        windows: List of windows for moving averages
        
    Returns:
        DataFrame with volume features added
        
    Examples:
        >>> df = calculate_volume_features(df, windows=[5, 10, 20])
        >>> print(df['volume_zscore'].tail())
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    df = df.copy()
    
    # Volume moving averages
    for window in windows:
        df[f'volume_ma_{window}'] = (
            df['volume'].rolling(window=window, min_periods=max(1, window // 2)).mean()
        )
    
    # Volume ratio (current vs 20-period average)
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20, min_periods=10).mean()
    
    # Volume z-score
    volume_mean = df['volume'].rolling(window=60, min_periods=20).mean()
    volume_std = df['volume'].rolling(window=60, min_periods=20).std()
    df['volume_zscore'] = (df['volume'] - volume_mean) / volume_std
    
    return df


def calculate_market_depth_proxy(
    df: pd.DataFrame,
    window: int = 20
) -> pd.Series:
    """
    Calculate proxy for market depth using volume and price range.
    
    Higher values suggest deeper markets (more liquidity at various price levels).
    
    Args:
        df: DataFrame with OHLC and volume data
        window: Rolling window for calculation
        
    Returns:
        Series with market depth proxy values
        
    Examples:
        >>> depth = calculate_market_depth_proxy(df, window=20)
        >>> print(f"Market depth: {depth.iloc[-1]:.2f}")
    """
    # Price range as proxy for volatility
    price_range = df['high'] - df['low']
    
    # Volume per unit of price range
    # Higher values mean more volume for less price movement = deeper market
    volume_per_range = df['volume'] / (price_range + 1e-8)  # Avoid division by zero
    
    # Normalize using rolling average
    depth_proxy = (
        volume_per_range /
        volume_per_range.rolling(window=window, min_periods=max(1, window // 2)).mean()
    )
    
    return depth_proxy


def session_liquidity_filter(
    index: pd.DatetimeIndex,
    block_windows: list = [(21, 23)],  # UTC hours to avoid (NY close / roll)
    timezone: str = "UTC"
) -> pd.Series:
    """
    Flag timestamps that fall inside illiquid windows so trades can be blocked.

    Args:
        index: DatetimeIndex for price/feature data
        block_windows: List of (start_hour, end_hour) tuples in 24h UTC
        timezone: Timezone of the index (converted to UTC for checking)

    Returns:
        Boolean Series aligned to index where True means "trade allowed"

    Examples:
        >>> mask = session_liquidity_filter(df.index, [(21, 23), (0, 1)])
        >>> df_filtered = df[mask]  # Drop illiquid bars
    """
    if index.tz is None:
        idx_utc = index.tz_localize(timezone).tz_convert("UTC")
    else:
        idx_utc = index.tz_convert("UTC")

    hours = idx_utc.hour
    allow = pd.Series(True, index=index)

    for start, end in block_windows:
        if start <= end:
            mask = (hours >= start) & (hours < end)
        else:
            # window wraps midnight
            mask = (hours >= start) | (hours < end)
        allow.loc[mask] = False

    return allow


def session_liquidity_score(
    index: pd.DatetimeIndex,
    timezone: str = "UTC"
) -> pd.Series:
    """
    Score liquidity by trading session (rough heuristic).

    Scores:
    - London/NY overlap (12-16 UTC): 1.0
    - London only (8-12 UTC): 0.8
    - NY only (16-20 UTC): 0.7
    - Asia (0-7 UTC): 0.4
    - Rollover / illiquid (21-23 UTC): 0.1

    Args:
        index: DatetimeIndex for data
        timezone: Timezone of index

    Returns:
        Series of liquidity scores in [0, 1]
    """
    if index.tz is None:
        idx_utc = index.tz_localize(timezone).tz_convert("UTC")
    else:
        idx_utc = index.tz_convert("UTC")

    hours = idx_utc.hour
    scores = pd.Series(0.5, index=index)  # default mid liquidity

    scores.loc[(hours >= 12) & (hours < 16)] = 1.0    # London/NY overlap
    scores.loc[(hours >= 8) & (hours < 12)] = 0.8     # London
    scores.loc[(hours >= 16) & (hours < 20)] = 0.7    # NY
    scores.loc[(hours >= 0) & (hours < 8)] = 0.4      # Asia
    scores.loc[(hours >= 21) & (hours < 24)] = 0.1    # Rollover / illiquid

    return scores
