"""
Return calculations for FX data.

Provides vectorized functions for calculating various types of returns
and volatility measures with proper NaN handling at boundaries.
"""

import numpy as np
import pandas as pd


def log_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate log returns.
    
    Log returns are more suitable for compounding and have better
    statistical properties than simple returns.
    
    Args:
        prices: Series of prices
        
    Returns:
        Series of log returns with NaN at first position
        
    Examples:
        >>> returns = log_returns(df['close'])
        >>> print(f"Mean daily return: {returns.mean():.6f}")
    """
    return np.log(prices / prices.shift(1))


def simple_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate simple returns.
    
    Simple returns are easier to interpret but don't compound properly.
    
    Args:
        prices: Series of prices
        
    Returns:
        Series of simple returns with NaN at first position
        
    Examples:
        >>> returns = simple_returns(df['close'])
        >>> print(f"Total return: {returns.sum():.2%}")
    """
    return prices.pct_change()


def rolling_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: int = 252,
    method: str = 'std'
) -> pd.Series:
    """
    Calculate rolling volatility.
    
    Args:
        returns: Series of returns
        window: Rolling window size
        annualize: Annualization factor (252 for daily, 252*24 for hourly)
        method: 'std' for standard deviation, 'ewm' for exponentially weighted
        
    Returns:
        Annualized rolling volatility
        
    Examples:
        >>> vol = rolling_volatility(returns, window=20, annualize=252)
        >>> print(f"Current volatility: {vol.iloc[-1]:.2%}")
    """
    if method == 'std':
        vol = returns.rolling(window=window, min_periods=max(1, window // 2)).std()
    elif method == 'ewm':
        vol = returns.ewm(span=window, min_periods=max(1, window // 2)).std()
    else:
        raise ValueError(f"Unknown method: {method}. Use 'std' or 'ewm'")
    
    # Annualize
    return vol * np.sqrt(annualize)


def parkinson_volatility(
    df: pd.DataFrame,
    window: int = 20,
    annualize: int = 252
) -> pd.Series:
    """
    Calculate Parkinson volatility estimator using high-low range.
    
    More efficient than close-to-close volatility.
    
    Args:
        df: DataFrame with 'high' and 'low' columns
        window: Rolling window size
        annualize: Annualization factor
        
    Returns:
        Annualized Parkinson volatility estimate
        
    Examples:
        >>> vol = parkinson_volatility(df, window=20)
        >>> print(f"Parkinson vol: {vol.iloc[-1]:.2%}")
    """
    # Parkinson formula: sqrt(1/(4*ln(2)) * mean((ln(H/L))^2))
    hl_ratio = np.log(df['high'] / df['low'])
    hl_ratio_sq = hl_ratio ** 2
    
    vol = np.sqrt(
        (1 / (4 * np.log(2))) *
        hl_ratio_sq.rolling(window=window, min_periods=max(1, window // 2)).mean()
    )
    
    # Annualize
    return vol * np.sqrt(annualize)


def garman_klass_volatility(
    df: pd.DataFrame,
    window: int = 20,
    annualize: int = 252
) -> pd.Series:
    """
    Calculate Garman-Klass volatility estimator using OHLC data.
    
    Even more efficient than Parkinson, considers open and close.
    
    Args:
        df: DataFrame with OHLC columns
        window: Rolling window size
        annualize: Annualization factor
        
    Returns:
        Annualized Garman-Klass volatility estimate
        
    Examples:
        >>> vol = garman_klass_volatility(df, window=20)
        >>> print(f"Garman-Klass vol: {vol.iloc[-1]:.2%}")
    """
    # Garman-Klass formula components
    log_hl = np.log(df['high'] / df['low'])
    log_co = np.log(df['close'] / df['open'])
    
    # GK = sqrt(0.5 * (log(H/L))^2 - (2*log(2)-1) * (log(C/O))^2)
    gk_component = 0.5 * (log_hl ** 2) - (2 * np.log(2) - 1) * (log_co ** 2)
    
    vol = np.sqrt(
        gk_component.rolling(window=window, min_periods=max(1, window // 2)).mean()
    )
    
    # Annualize
    return vol * np.sqrt(annualize)


def realized_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: int = 252
) -> pd.Series:
    """
    Calculate realized volatility (sum of squared returns).
    
    Args:
        returns: Series of returns
        window: Rolling window size
        annualize: Annualization factor
        
    Returns:
        Annualized realized volatility
        
    Examples:
        >>> rv = realized_volatility(returns, window=20)
        >>> print(f"Realized vol: {rv.iloc[-1]:.2%}")
    """
    rv = np.sqrt(
        (returns ** 2).rolling(window=window, min_periods=max(1, window // 2)).sum()
    )
    
    # Annualize
    return rv * np.sqrt(annualize / window)


def multi_period_returns(
    prices: pd.Series,
    periods: list = [1, 5, 10, 20]
) -> pd.DataFrame:
    """
    Calculate returns over multiple periods.
    
    Args:
        prices: Series of prices
        periods: List of periods to calculate returns over
        
    Returns:
        DataFrame with returns for each period
        
    Examples:
        >>> multi_ret = multi_period_returns(df['close'], [1, 5, 10, 20])
        >>> print(multi_ret.tail())
    """
    returns_df = pd.DataFrame(index=prices.index)
    
    for period in periods:
        returns_df[f'return_{period}d'] = prices.pct_change(period)
    
    return returns_df
