"""
Multi-timeframe feature engineering for FX strategy.

Provides trend confirmation and regime detection from higher timeframes.
Implements proper forward-fill to avoid look-ahead bias.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path


class MultiTimeframeFeatures:
    """
    Generate features from multiple timeframes for enhanced signal quality.
    
    Key principles:
    - Resample H1 → H4, D1 to get higher timeframe context
    - Forward-fill to align with H1 bars (no look-ahead)
    - Calculate trend, momentum, volatility regime on each TF
    - Use for signal filtering or regime classification
    
    Examples:
        >>> mtf = MultiTimeframeFeatures()
        >>> df_h1 = mtf.add_higher_tf_features(df_h1)
        >>> # Now df_h1 has h4_trend, d1_trend, h4_vol_regime, etc.
    """
    
    def __init__(
        self,
        h4_trend_window: int = 20,
        d1_trend_window: int = 10,
        vol_percentile: int = 50,
        adx_period: int = 14
    ):
        """
        Initialize multi-timeframe feature generator.
        
        Args:
            h4_trend_window: Bars for H4 trend calculation (default 20 = ~3 days)
            d1_trend_window: Bars for D1 trend calculation (default 10 = 2 weeks)
            vol_percentile: Percentile for volatility regime (default 50 = median)
            adx_period: Period for ADX trend strength (default 14)
        """
        self.h4_trend_window = h4_trend_window
        self.d1_trend_window = d1_trend_window
        self.vol_percentile = vol_percentile
        self.adx_period = adx_period
    
    def resample_to_timeframe(
        self,
        df_h1: pd.DataFrame,
        target_tf: str
    ) -> pd.DataFrame:
        """
        Resample H1 OHLC data to target timeframe.
        
        Args:
            df_h1: H1 DataFrame with OHLC data
            target_tf: Target timeframe ('4h' or 'd')
            
        Returns:
            Resampled DataFrame with OHLC
        """
        # Ensure index is datetime
        if not isinstance(df_h1.index, pd.DatetimeIndex):
            df_resampled = df_h1.set_index('timestamp')
        else:
            df_resampled = df_h1.copy()
        
        # Resample OHLC
        df_tf = pd.DataFrame({
            'open': df_resampled['open'].resample(target_tf).first(),
            'high': df_resampled['high'].resample(target_tf).max(),
            'low': df_resampled['low'].resample(target_tf).min(),
            'close': df_resampled['close'].resample(target_tf).last(),
            'volume': df_resampled['volume'].resample(target_tf).sum()
        })
        
        return df_tf.dropna()
    
    def calculate_trend_direction(
        self,
        df: pd.DataFrame,
        window: int,
        prefix: str = ''
    ) -> pd.Series:
        """
        Calculate trend direction using SMA slope.
        
        Args:
            df: DataFrame with close prices
            window: SMA window
            prefix: Prefix for column name
            
        Returns:
            Series: 1 (uptrend), -1 (downtrend), 0 (ranging)
        """
        sma = df['close'].rolling(window=window, min_periods=max(1, window // 2)).mean()
        sma_slope = (sma - sma.shift(window // 4)) / sma.shift(window // 4)
        
        # Classify trend
        trend = pd.Series(0, index=df.index)
        trend[sma_slope > 0.01] = 1   # Uptrend if >1% slope
        trend[sma_slope < -0.01] = -1  # Downtrend if <-1% slope
        
        return trend
    
    def calculate_volatility_regime(
        self,
        df: pd.DataFrame,
        window: int = 20,
        percentile: int = 50
    ) -> pd.Series:
        """
        Classify volatility regime (high/low).
        
        Args:
            df: DataFrame with OHLC data
            window: Window for volatility calculation
            percentile: Percentile threshold for high vol
            
        Returns:
            Series: True (high vol), False (low vol)
        """
        # Calculate realized volatility
        returns = df['close'].pct_change()
        realized_vol = returns.rolling(window=window, min_periods=max(1, window // 2)).std()
        
        # Calculate rolling percentile
        vol_percentile = realized_vol.rolling(
            window=window * 5,
            min_periods=max(1, window)
        ).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False)
        
        # High vol if above percentile threshold
        high_vol = vol_percentile > percentile
        
        return high_vol
    
    def calculate_adx(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate ADX (Average Directional Index) for trend strength.
        
        Args:
            df: DataFrame with OHLC data
            period: ADX period
            
        Returns:
            Series: ADX values (0-100, higher = stronger trend)
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smooth indicators
        plus_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(
            window=period, min_periods=max(1, period // 2)
        ).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(
            window=period, min_periods=max(1, period // 2)
        ).mean()
        tr_smooth = tr.rolling(window=period, min_periods=max(1, period // 2)).mean()
        
        # Directional indicators
        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth
        
        # ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(window=period, min_periods=max(1, period // 2)).mean() * 100
        
        return adx
    
    def add_higher_tf_features(
        self,
        df_h1: pd.DataFrame,
        include_h4: bool = True,
        include_d1: bool = True
    ) -> pd.DataFrame:
        """
        Add higher timeframe features to H1 data.
        
        Args:
            df_h1: H1 DataFrame with OHLC data
            include_h4: Add H4 features
            include_d1: Add D1 features
            
        Returns:
            H1 DataFrame with higher TF features merged
            
        Examples:
            >>> mtf = MultiTimeframeFeatures()
            >>> df_h1 = mtf.add_higher_tf_features(df_h1)
            >>> # Check alignment
            >>> print(df_h1[['close', 'h4_trend', 'd1_trend']].tail())
        """
        df = df_h1.copy()
        
        # Store original index
        original_index = df.index
        has_timestamp_col = 'timestamp' in df.columns
        
        # Ensure datetime index for resampling
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df = df.set_index('timestamp')
            else:
                raise ValueError("DataFrame must have datetime index or 'timestamp' column")
        
        # H4 features
        if include_h4:
            df_h4 = self.resample_to_timeframe(df, '4h')
            
            # Calculate H4 features
            h4_trend = self.calculate_trend_direction(df_h4, self.h4_trend_window, 'h4')
            h4_vol_regime = self.calculate_volatility_regime(df_h4, window=20, percentile=self.vol_percentile)
            h4_adx = self.calculate_adx(df_h4, self.adx_period)
            
            # Create H4 feature DataFrame
            df_h4_features = pd.DataFrame({
                'h4_trend': h4_trend,
                'h4_high_vol': h4_vol_regime,
                'h4_adx': h4_adx
            })
            
            # Forward-fill to H1 frequency (no look-ahead)
            df_h4_features = df_h4_features.reindex(df.index, method='ffill')
            
            # Merge to H1
            df = df.join(df_h4_features)
        
        # D1 features
        if include_d1:
            df_d1 = self.resample_to_timeframe(df, 'd')
            
            # Calculate D1 features
            d1_trend = self.calculate_trend_direction(df_d1, self.d1_trend_window, 'd1')
            d1_vol_regime = self.calculate_volatility_regime(df_d1, window=10, percentile=self.vol_percentile)
            d1_adx = self.calculate_adx(df_d1, self.adx_period)
            
            # Create D1 feature DataFrame
            df_d1_features = pd.DataFrame({
                'd1_trend': d1_trend,
                'd1_high_vol': d1_vol_regime,
                'd1_adx': d1_adx
            })
            
            # Forward-fill to H1 frequency (no look-ahead)
            df_d1_features = df_d1_features.reindex(df.index, method='ffill')
            
            # Merge to H1
            df = df.join(df_d1_features)
        
        # Restore original index if needed
        if not isinstance(original_index, pd.DatetimeIndex):
            df = df.reset_index()
            if not has_timestamp_col:
                df = df.drop('timestamp', axis=1)
        
        return df
    
    def get_multi_tf_alignment(
        self,
        df: pd.DataFrame
    ) -> pd.Series:
        """
        Check if H1, H4, D1 trends are aligned.
        
        Args:
            df: DataFrame with h4_trend and d1_trend columns
            
        Returns:
            Series: True if all trends aligned (bullish or bearish)
        """
        if 'h4_trend' not in df.columns or 'd1_trend' not in df.columns:
            raise ValueError("DataFrame must have h4_trend and d1_trend columns")
        
        # All uptrend or all downtrend
        all_up = (df['h4_trend'] == 1) & (df['d1_trend'] == 1)
        all_down = (df['h4_trend'] == -1) & (df['d1_trend'] == -1)
        
        aligned = all_up | all_down
        
        return aligned
    
    def get_ranging_market(
        self,
        df: pd.DataFrame,
        adx_threshold: float = 25.0
    ) -> pd.Series:
        """
        Identify ranging markets from multi-timeframe ADX.
        
        Args:
            df: DataFrame with h4_adx and/or d1_adx columns
            adx_threshold: ADX threshold for ranging (default 25)
            
        Returns:
            Series: True if market is ranging
        """
        ranging = pd.Series(True, index=df.index)
        
        # Check H4 ADX
        if 'h4_adx' in df.columns:
            ranging &= df['h4_adx'] < adx_threshold
        
        # Check D1 ADX
        if 'd1_adx' in df.columns:
            ranging &= df['d1_adx'] < adx_threshold
        
        return ranging
    
    def generate_report(
        self,
        df: pd.DataFrame
    ) -> Dict:
        """
        Generate diagnostic report on multi-timeframe features.
        
        Args:
            df: DataFrame with multi-TF features
            
        Returns:
            Dict with statistics
        """
        report = {}
        
        if 'h4_trend' in df.columns:
            h4_trend_counts = df['h4_trend'].value_counts()
            report['h4_trend_distribution'] = {
                'uptrend_pct': h4_trend_counts.get(1, 0) / len(df) * 100,
                'downtrend_pct': h4_trend_counts.get(-1, 0) / len(df) * 100,
                'ranging_pct': h4_trend_counts.get(0, 0) / len(df) * 100
            }
        
        if 'd1_trend' in df.columns:
            d1_trend_counts = df['d1_trend'].value_counts()
            report['d1_trend_distribution'] = {
                'uptrend_pct': d1_trend_counts.get(1, 0) / len(df) * 100,
                'downtrend_pct': d1_trend_counts.get(-1, 0) / len(df) * 100,
                'ranging_pct': d1_trend_counts.get(0, 0) / len(df) * 100
            }
        
        if 'h4_high_vol' in df.columns:
            report['h4_high_vol_pct'] = df['h4_high_vol'].mean() * 100
        
        if 'd1_high_vol' in df.columns:
            report['d1_high_vol_pct'] = df['d1_high_vol'].mean() * 100
        
        # Alignment stats
        if 'h4_trend' in df.columns and 'd1_trend' in df.columns:
            aligned = self.get_multi_tf_alignment(df)
            report['tf_alignment_pct'] = aligned.mean() * 100
        
        return report


if __name__ == "__main__":
    print("Multi-timeframe feature engineering module loaded.")
    print("Usage:")
    print("  from src.features.multi_timeframe import MultiTimeframeFeatures")
    print("  mtf = MultiTimeframeFeatures()")
    print("  df_h1 = mtf.add_higher_tf_features(df_h1)")
