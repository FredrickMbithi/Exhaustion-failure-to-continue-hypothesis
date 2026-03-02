"""
Data validation module for FX OHLC data.

Provides comprehensive validation including OHLC logic checks, spike detection,
missing bar identification, and spread validation.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import median_abs_deviation


class ValidationReport(BaseModel):
    """Structured validation report."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class DataValidator:
    """
    Comprehensive validator for FX OHLC data.
    
    Performs validation checks including:
    - OHLC logic consistency
    - Missing bar detection
    - Spike detection using z-scores and MAD
    - Spread validation
    
    Examples:
        >>> validator = DataValidator(spike_threshold=5.0)
        >>> report = validator.validate(df)
        >>> if not report.is_valid:
        ...     print("\\n".join(report.errors))
    """
    
    def __init__(
        self,
        spike_threshold: float = 5.0,
        max_missing_pct: float = 5.0,
        validate_ohlc: bool = True
    ):
        """
        Initialize validator with thresholds.
        
        Args:
            spike_threshold: Standard deviations threshold for spike detection
            max_missing_pct: Maximum allowed missing data percentage
            validate_ohlc: Whether to validate OHLC logic
        """
        self.spike_threshold = spike_threshold
        self.max_missing_pct = max_missing_pct
        self.validate_ohlc = validate_ohlc
    
    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Run all validation checks on DataFrame.
        
        Args:
            df: DataFrame with OHLC data and DatetimeIndex
            
        Returns:
            ValidationReport with results of all checks
            
        Examples:
            >>> report = validator.validate(df)
            >>> assert report.is_valid, f"Validation failed: {report.errors}"
        """
        errors = []
        warnings = []
        metrics = {}
        
        # Check OHLC logic
        if self.validate_ohlc:
            ohlc_valid, ohlc_errors = self.validate_ohlc_logic(df)
            if not ohlc_valid:
                errors.extend(ohlc_errors)
            metrics['ohlc_valid'] = ohlc_valid
        
        # Detect missing bars
        missing_bars = self.detect_missing_bars(df, freq='D')
        missing_pct = (len(missing_bars) / len(df)) * 100 if len(df) > 0 else 0
        metrics['missing_bars_count'] = len(missing_bars)
        metrics['missing_bars_pct'] = missing_pct
        
        if missing_pct > self.max_missing_pct:
            errors.append(f"Missing data {missing_pct:.2f}% exceeds threshold {self.max_missing_pct}%")
        elif len(missing_bars) > 0:
            warnings.append(f"Found {len(missing_bars)} missing bars")
        
        # Detect spikes
        spike_mask = self.detect_spikes(df, threshold=self.spike_threshold)
        spike_count = spike_mask.sum()
        metrics['spike_count'] = int(spike_count)
        metrics['spike_pct'] = (spike_count / len(df)) * 100 if len(df) > 0 else 0
        
        if spike_count > 0:
            warnings.append(
                f"Detected {spike_count} spikes (> {self.spike_threshold}σ). "
                f"Timestamps: {df.index[spike_mask].tolist()[:5]}"
            )
        
        # Validate spread if present
        if 'spread' in df.columns:
            spread_valid, spread_msg = self.validate_spread(df)
            metrics['spread_valid'] = spread_valid
            if not spread_valid:
                errors.append(spread_msg)
        
        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metrics=metrics
        )
    
    def validate_ohlc_logic(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate OHLC logic: high >= max(open, close, low) and low <= min(open, close, high).
        
        Args:
            df: DataFrame with OHLC columns
            
        Returns:
            Tuple of (is_valid, list of error messages)
            
        Examples:
            >>> valid, errors = validator.validate_ohlc_logic(df)
            >>> assert valid, f"OHLC validation failed: {errors}"
        """
        errors = []
        
        # Check high is highest
        high_invalid = (
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['high'] < df['low'])
        )
        
        if high_invalid.any():
            count = high_invalid.sum()
            errors.append(
                f"High price validation failed for {count} bars. "
                f"High must be >= max(open, close, low)"
            )
        
        # Check low is lowest
        low_invalid = (
            (df['low'] > df['open']) |
            (df['low'] > df['close']) |
            (df['low'] > df['high'])
        )
        
        if low_invalid.any():
            count = low_invalid.sum()
            errors.append(
                f"Low price validation failed for {count} bars. "
                f"Low must be <= min(open, close, high)"
            )
        
        return len(errors) == 0, errors
    
    def detect_missing_bars(
        self,
        df: pd.DataFrame,
        freq: str = 'D'
    ) -> List[pd.Timestamp]:
        """
        Detect missing bars by comparing against expected business day schedule.
        
        Args:
            df: DataFrame with DatetimeIndex
            freq: Expected frequency ('D' for daily, 'H' for hourly, etc.)
            
        Returns:
            List of missing timestamps (excluding weekends for daily data)
            
        Examples:
            >>> missing = validator.detect_missing_bars(df, freq='D')
            >>> print(f"Missing bars: {len(missing)}")
        """
        if len(df) == 0:
            return []
        
        # Generate expected date range
        if freq == 'D':
            # For FX, use business days (Mon-Fri)
            expected_dates = pd.bdate_range(
                start=df.index[0],
                end=df.index[-1],
                freq='B'  # Business days
            )
        else:
            expected_dates = pd.date_range(
                start=df.index[0],
                end=df.index[-1],
                freq=freq
            )
        
        # Find missing dates
        missing = expected_dates.difference(df.index)
        
        return list(missing)
    
    def detect_spikes(
        self,
        df: pd.DataFrame,
        threshold: float = 5.0
    ) -> pd.Series:
        """
        Detect price spikes using z-scores and Median Absolute Deviation (MAD).
        
        Uses both z-score and MAD for robustness. MAD is more resistant to outliers.
        
        Args:
            df: DataFrame with close prices
            threshold: Standard deviation threshold for spike detection
            
        Returns:
            Boolean Series indicating spike locations
            
        Examples:
            >>> spikes = validator.detect_spikes(df, threshold=5.0)
            >>> print(f"Detected {spikes.sum()} spikes")
        """
        if len(df) < 2:
            return pd.Series(False, index=df.index)
        
        # Calculate log returns
        returns = np.log(df['close'] / df['close'].shift(1))
        
        # Z-score method
        rolling_mean = returns.rolling(window=20, min_periods=1).mean()
        rolling_std = returns.rolling(window=20, min_periods=1).std()
        z_scores = (returns - rolling_mean) / rolling_std
        
        # MAD method (more robust to outliers)
        mad = median_abs_deviation(returns.dropna(), nan_policy='omit')
        median_return = returns.median()
        mad_scores = np.abs(returns - median_return) / (mad + 1e-8)  # Avoid division by zero
        
        # Flag as spike if either method exceeds threshold
        spikes = (np.abs(z_scores) > threshold) | (mad_scores > threshold)
        
        return spikes.fillna(False)
    
    def validate_spread(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate spread data if present.
        
        Checks that spreads are:
        - Positive
        - Within reasonable ranges for FX
        - Not constant (which would indicate bad data)
        
        Args:
            df: DataFrame with optional 'spread' column
            
        Returns:
            Tuple of (is_valid, message)
            
        Examples:
            >>> valid, msg = validator.validate_spread(df)
            >>> if not valid:
            ...     print(f"Spread validation failed: {msg}")
        """
        if 'spread' not in df.columns:
            return True, "No spread column to validate"
        
        spread = df['spread']
        
        # Check for negative spreads
        if (spread < 0).any():
            negative_count = (spread < 0).sum()
            return False, f"Found {negative_count} negative spread values"
        
        # Check if all spreads are zero (bad data)
        if (spread == 0).all():
            return False, "All spreads are zero - likely bad data"
        
        # Check if spreads are constant (suspicious)
        if spread.nunique() == 1:
            return False, f"All spreads are identical ({spread.iloc[0]}) - suspicious"
        
        # Check for unreasonably large spreads (>100 pips for majors is suspicious)
        mid_price = (df['high'] + df['low']) / 2
        spread_pct = (spread / mid_price) * 100
        
        if (spread_pct > 1.0).any():  # >1% spread is unusual for FX
            outlier_count = (spread_pct > 1.0).sum()
            return False, f"Found {outlier_count} spreads exceeding 1% of price - check data quality"
        
        return True, "Spread validation passed"
