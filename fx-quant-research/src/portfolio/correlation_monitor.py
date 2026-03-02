"""
Correlation monitoring and structural break detection.

Tracks correlation stability and alerts on regime changes.
"""

from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats


class CorrelationMonitor:
    """
    Monitor correlation stability and detect structural breaks.
    
    Tracks correlation patterns over time and flags significant changes
    that may indicate regime shifts.
    
    Examples:
        >>> monitor = CorrelationMonitor(window=120)
        >>> monitor.fit(returns_df)
        >>> alerts = monitor.check_for_breaks(returns_df_recent)
    """
    
    def __init__(
        self,
        window: int = 120,
        break_threshold: float = 0.3
    ):
        """
        Initialize correlation monitor.
        
        Args:
            window: Historical window for baseline correlation
            break_threshold: Minimum change to flag as structural break
        """
        self.window = window
        self.break_threshold = break_threshold
        self.baseline_correlations = None
        self.is_fitted = False
    
    def fit(self, returns_df: pd.DataFrame) -> 'CorrelationMonitor':
        """
        Fit monitor to historical data to establish baseline.
        
        Args:
            returns_df: DataFrame with historical returns
            
        Returns:
            Self (fitted monitor)
        """
        if len(returns_df) < self.window:
            raise ValueError(f"Need at least {self.window} samples for baseline")
        
        # Calculate baseline correlation matrix
        self.baseline_correlations = returns_df.tail(self.window).corr()
        self.asset_names = list(returns_df.columns)
        self.is_fitted = True
        
        return self
    
    def check_for_breaks(
        self,
        recent_returns: pd.DataFrame,
        window: Optional[int] = None
    ) -> List[Dict]:
        """
        Check for correlation structural breaks.
        
        Args:
            recent_returns: Recent returns data
            window: Window for recent correlation (default: self.window // 2)
            
        Returns:
            List of alert dictionaries for detected breaks
            
        Examples:
            >>> alerts = monitor.check_for_breaks(recent_returns)
            >>> for alert in alerts:
            ...     print(f"Break detected: {alert['pair']}, change: {alert['change']:.3f}")
        """
        if not self.is_fitted:
            raise ValueError("Monitor not fitted. Call fit() first.")
        
        window = window or (self.window // 2)
        
        if len(recent_returns) < window:
            raise ValueError(f"Need at least {window} samples for recent correlation")
        
        # Calculate recent correlation
        recent_corr = recent_returns.tail(window).corr()
        
        # Compare to baseline
        alerts = []
        
        for i, asset1 in enumerate(self.asset_names):
            for j, asset2 in enumerate(self.asset_names):
                if i < j:  # Avoid duplicates
                    if asset1 in recent_corr.index and asset2 in recent_corr.columns:
                        baseline = self.baseline_correlations.loc[asset1, asset2]
                        current = recent_corr.loc[asset1, asset2]
                        
                        change = abs(current - baseline)
                        
                        if change > self.break_threshold:
                            alerts.append({
                                'pair': f'{asset1}-{asset2}',
                                'baseline_corr': float(baseline),
                                'current_corr': float(current),
                                'change': float(change),
                                'direction': 'increase' if current > baseline else 'decrease'
                            })
        
        return alerts
    
    def detect_structural_break(
        self,
        corr_series: pd.Series,
        test_window: int = 120
    ) -> Tuple[bool, Dict]:
        """
        Detect structural break using statistical test.
        
        Uses Chow test to detect if correlation regime has changed.
        
        Args:
            corr_series: Time series of correlation values
            test_window: Window size for test
            
        Returns:
            Tuple of (break_detected, test_statistics)
            
        Examples:
            >>> has_break, stats = monitor.detect_structural_break(corr_ts)
            >>> if has_break:
            ...     print(f"Structural break detected: p-value = {stats['p_value']:.4f}")
        """
        if len(corr_series) < test_window * 2:
            return False, {'error': 'Insufficient data for test'}
        
        # Split into two periods
        split_point = len(corr_series) - test_window
        period1 = corr_series.iloc[:split_point]
        period2 = corr_series.iloc[split_point:]
        
        # Two-sample t-test
        t_stat, p_value = stats.ttest_ind(period1.dropna(), period2.dropna())
        
        # Also check for variance change (F-test)
        var1 = period1.var()
        var2 = period2.var()
        f_stat = var1 / var2 if var2 > 0 else 0.0
        
        break_detected = p_value < 0.05  # Significant at 5% level
        
        return break_detected, {
            't_statistic': float(t_stat),
            'p_value': float(p_value),
            'f_statistic': float(f_stat),
            'mean_period1': float(period1.mean()),
            'mean_period2': float(period2.mean()),
            'var_period1': float(var1),
            'var_period2': float(var2)
        }
    
    def rolling_correlation_stability(
        self,
        returns_df: pd.DataFrame,
        window: int = 60,
        step: int = 20
    ) -> pd.DataFrame:
        """
        Calculate rolling correlation stability metric.
        
        Measures how stable pairwise correlations are over time.
        
        Args:
            returns_df: DataFrame with returns
            window: Window for correlation calculation
            step: Step size for rolling calculation
            
        Returns:
            DataFrame with stability metrics over time
            
        Examples:
            >>> stability = monitor.rolling_correlation_stability(returns_df)
            >>> print(stability.tail())
        """
        timestamps = []
        stability_scores = []
        
        for i in range(window, len(returns_df) - step, step):
            window_data = returns_df.iloc[i-window:i]
            future_data = returns_df.iloc[i:i+step]
            
            if len(future_data) == step:
                # Current correlation
                current_corr = window_data.corr()
                
                # Future correlation
                future_corr = future_data.corr()
                
                # Measure stability as correlation between correlation matrices
                # Flatten matrices to vectors (upper triangle only)
                n = len(current_corr)
                current_vec = []
                future_vec = []
                
                for row in range(n):
                    for col in range(row+1, n):
                        current_vec.append(current_corr.iloc[row, col])
                        future_vec.append(future_corr.iloc[row, col])
                
                # Correlation of correlations
                if len(current_vec) > 0:
                    stability = np.corrcoef(current_vec, future_vec)[0, 1]
                else:
                    stability = 1.0
                
                timestamps.append(returns_df.index[i])
                stability_scores.append(stability)
        
        return pd.DataFrame({
            'stability': stability_scores
        }, index=timestamps)


def calculate_correlation_dispersion(corr_matrix: pd.DataFrame) -> float:
    """
    Calculate dispersion of correlations.
    
    Measures how spread out pairwise correlations are.
    Lower dispersion indicates more uniform correlation structure.
    
    Args:
        corr_matrix: Correlation matrix
        
    Returns:
        Standard deviation of off-diagonal correlations
        
    Examples:
        >>> dispersion = calculate_correlation_dispersion(corr_matrix)
        >>> print(f"Correlation dispersion: {dispersion:.3f}")
    """
    # Extract off-diagonal elements
    n = len(corr_matrix)
    off_diag = []
    
    for i in range(n):
        for j in range(i+1, n):
            off_diag.append(corr_matrix.iloc[i, j])
    
    return float(np.std(off_diag)) if off_diag else 0.0
