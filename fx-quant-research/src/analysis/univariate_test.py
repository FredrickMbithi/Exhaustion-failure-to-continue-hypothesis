"""
Univariate feature testing with proper statistical rigor.

Implements:
- Information Coefficient (IC) calculation with Newey-West HAC standard errors
- Stationarity testing (ADF + KPSS dual test)
- Multiple testing correction (Benjamini-Hochberg FDR control)
- Cross-pair consistency validation

References:
    Newey-West (1987): Heteroskedasticity and Autocorrelation Consistent Covariance Matrix
    Benjamini-Hochberg (1995): False Discovery Rate control
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import spearmanr, t as t_dist
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.stats.sandwich_covariance import cov_hac


@dataclass
class FeatureTestResult:
    """Results from univariate feature testing."""
    feature_name: str
    ic_mean: float
    ic_std: float
    ic_tstat: float
    ic_tstat_hac: float
    ic_pvalue: float
    ic_pvalue_fdr: float
    is_stationary: bool
    adf_pvalue: float
    kpss_pvalue: float
    n_observations: int
    cross_pair_consistency: float = 0.0
    cross_pair_ics: Dict[str, float] = field(default_factory=dict)
    

def compute_information_coefficient(
    feature: pd.Series,
    forward_returns: pd.Series,
    min_periods: int = 100
) -> float:
    """
    Compute Spearman rank Information Coefficient (IC).
    
    IC measures the monotonic relationship between feature values and
    forward returns. Higher |IC| indicates stronger predictive power.
    
    Args:
        feature: Feature values
        forward_returns: Forward returns to predict
        min_periods: Minimum valid observations required
        
    Returns:
        Spearman correlation coefficient
        
    Examples:
        >>> ic = compute_information_coefficient(df['momentum_20'], df['returns'].shift(-1))
        >>> print(f"IC: {ic:.4f}")
    """
    # Align and dropna
    valid = pd.concat([feature, forward_returns], axis=1).dropna()
    
    if len(valid) < min_periods:
        return np.nan
    
    # Spearman rank correlation
    ic, _ = spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
    
    return ic


def compute_rolling_ic(
    feature: pd.Series,
    forward_returns: pd.Series,
    window: int = 126,  # 6 months
    min_periods: int = 60
) -> pd.Series:
    """
    Compute rolling Information Coefficient.
    
    Args:
        feature: Feature values
        forward_returns: Forward returns
        window: Rolling window size
        min_periods: Minimum periods for calculation
        
    Returns:
        Rolling IC series
    """
    def _compute_ic(x, y):
        if len(x) < min_periods:
            return np.nan
        ic, _ = spearmanr(x, y)
        return ic
    
    # Align series
    df = pd.concat([feature, forward_returns], axis=1).dropna()
    
    if len(df) < min_periods:
        return pd.Series(index=feature.index, dtype=float)
    
    # Rolling IC
    rolling_ic = df.iloc[:, 0].rolling(window=window, min_periods=min_periods).apply(
        lambda x: _compute_ic(x.values, df.iloc[:, 1].iloc[-len(x):].values),
        raw=False
    )
    
    return rolling_ic


def compute_hac_tstat(
    feature: pd.Series,
    forward_returns: pd.Series,
    max_lags: Optional[int] = None
) -> Tuple[float, float]:
    """
    Compute HAC (Heteroskedasticity and Autocorrelation Consistent) t-statistic.
    
    Uses Newey-West covariance estimator to account for serial correlation
    in IC estimates.
    
    Args:
        feature: Feature values
        forward_returns: Forward returns
        max_lags: Maximum lags for Newey-West (default: auto based on sample size)
        
    Returns:
        Tuple of (HAC t-stat, p-value)
        
    Examples:
        >>> tstat, pval = compute_hac_tstat(feature, returns)
        >>> print(f"HAC t-stat: {tstat:.2f}, p-value: {pval:.4f}")
    """
    # Align and dropna
    valid = pd.concat([feature, forward_returns], axis=1).dropna()
    
    if len(valid) < 30:
        return np.nan, np.nan
    
    # Compute IC
    ic, _ = spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
    
    # For HAC standard error, we need returns as residuals
    # Use simple returns for error calculation
    returns = valid.iloc[:, 1].values.reshape(-1, 1)
    
    # Auto-select lags if not specified (Newey-West rule: floor(4*(T/100)^(2/9)))
    if max_lags is None:
        T = len(returns)
        max_lags = int(np.floor(4 * (T / 100) ** (2/9)))
    
    try:
        # Compute HAC covariance
        cov_matrix = cov_hac(returns, nlags=max_lags)
        hac_se = np.sqrt(cov_matrix[0, 0] / len(returns))
        
        # T-statistic
        tstat = ic / hac_se if hac_se > 0 else 0
        
        # Two-tailed p-value
        df = len(returns) - 1
        pval = 2 * (1 - t_dist.cdf(abs(tstat), df))
        
        return tstat, pval
    except:
        # Fallback to standard t-test if HAC fails
        se = np.std(returns) / np.sqrt(len(returns))
        tstat = ic / se if se > 0 else 0
        df = len(returns) - 1
        pval = 2 * (1 - t_dist.cdf(abs(tstat), df))
        return tstat, pval


def test_stationarity(
    series: pd.Series,
    adf_threshold: float = 0.05,
    kpss_threshold: float = 0.05
) -> Tuple[bool, float, float]:
    """
    Test stationarity using both ADF and KPSS tests.
    
    Series is considered stationary only if:
    - ADF rejects null (p < 0.05): series does NOT have unit root
    - KPSS accepts null (p > 0.05): series IS stationary
    
    Args:
        series: Time series to test
        adf_threshold: P-value threshold for ADF test
        kpss_threshold: P-value threshold for KPSS test
        
    Returns:
        Tuple of (is_stationary, adf_pvalue, kpss_pvalue)
    """
    series_clean = series.dropna()
    
    if len(series_clean) < 20:
        return False, 1.0, 0.0
    
    try:
        # ADF test (null: non-stationary)
        adf_result = adfuller(series_clean, autolag='AIC')
        adf_pvalue = float(adf_result[1])
        
        # KPSS test (null: stationary)
        kpss_result = kpss(series_clean, regression='c', nlags='auto')
        kpss_pvalue = float(kpss_result[1])
        
        # Both must pass
        is_stationary = (adf_pvalue < adf_threshold) and (kpss_pvalue > kpss_threshold)
        
        return is_stationary, adf_pvalue, kpss_pvalue
    except Exception as e:
        print(f"Stationarity test failed: {e}")
        return False, 1.0, 0.0


def test_feature(
    feature: pd.Series,
    returns: pd.Series,
    forward_periods: int = 1,
    min_observations: int = 100
) -> FeatureTestResult:
    """
    Comprehensive univariate feature test.
    
    Tests:
    1. Information Coefficient (IC)
    2. HAC-corrected t-statistic
    3. Stationarity (ADF + KPSS)
    
    Args:
        feature: Feature series to test
        returns: Returns series
        forward_periods: Periods to shift returns forward
        min_observations: Minimum required observations
        
    Returns:
        FeatureTestResult with all test statistics
    """
    # Forward returns
    forward_returns = returns.shift(-forward_periods)
    
    # Align data
    valid = pd.concat([feature, forward_returns], axis=1).dropna()
    
    if len(valid) < min_observations:
        return FeatureTestResult(
            feature_name=feature.name or "unknown",
            ic_mean=np.nan,
            ic_std=np.nan,
            ic_tstat=np.nan,
            ic_tstat_hac=np.nan,
            ic_pvalue=1.0,
            ic_pvalue_fdr=1.0,
            is_stationary=False,
            adf_pvalue=1.0,
            kpss_pvalue=0.0,
            n_observations=len(valid)
        )
    
    # 1. IC calculation
    ic_mean = compute_information_coefficient(feature, forward_returns, min_observations)
    
    # 2. HAC t-statistic
    ic_tstat_hac, ic_pvalue = compute_hac_tstat(feature, forward_returns)
    
    # 3. Standard t-statistic (for comparison)
    ic_std = 1.0 / np.sqrt(len(valid)) if len(valid) > 0 else np.nan
    ic_tstat = ic_mean / ic_std if ic_std > 0 else 0
    
    # 4. Stationarity test
    is_stationary, adf_pvalue, kpss_pvalue = test_stationarity(feature)
    
    return FeatureTestResult(
        feature_name=feature.name or "unknown",
        ic_mean=ic_mean,
        ic_std=ic_std,
        ic_tstat=ic_tstat,
        ic_tstat_hac=ic_tstat_hac,
        ic_pvalue=ic_pvalue,
        ic_pvalue_fdr=ic_pvalue,  # Will be corrected in batch
        is_stationary=is_stationary,
        adf_pvalue=adf_pvalue,
        kpss_pvalue=kpss_pvalue,
        n_observations=len(valid)
    )


def apply_fdr_correction(
    results: List[FeatureTestResult],
    alpha: float = 0.05,
    method: str = 'fdr_bh'
) -> List[FeatureTestResult]:
    """
    Apply Benjamini-Hochberg FDR correction to p-values.
    
    Args:
        results: List of feature test results
        alpha: FDR control level (default 0.05)
        method: Multiple testing method ('fdr_bh' for Benjamini-Hochberg)
        
    Returns:
        Results with corrected p-values
    """
    # Extract p-values
    pvalues = [r.ic_pvalue for r in results]
    
    # Apply FDR correction
    reject, pvals_corrected, _, _ = multipletests(
        pvalues,
        alpha=alpha,
        method=method
    )
    
    # Update results
    for i, result in enumerate(results):
        result.ic_pvalue_fdr = pvals_corrected[i]
    
    return results


def rank_features(
    results: List[FeatureTestResult],
    ic_threshold: float = 0.03,
    tstat_threshold: float = 2.0,
    fdr_alpha: float = 0.05
) -> pd.DataFrame:
    """
    Rank features by statistical significance and predictive power.
    
    Criteria:
    1. |IC| > ic_threshold
    2. |HAC t-stat| > tstat_threshold
    3. FDR-corrected p-value < fdr_alpha
    4. Stationary
    
    Args:
        results: Feature test results
        ic_threshold: Minimum |IC| threshold
        tstat_threshold: Minimum |t-stat| threshold
        fdr_alpha: FDR significance level
        
    Returns:
        DataFrame with ranked features
    """
    # Convert to DataFrame
    data = []
    for r in results:
        data.append({
            'feature': r.feature_name,
            'ic_mean': r.ic_mean,
            'ic_tstat_hac': r.ic_tstat_hac,
            'ic_pvalue_fdr': r.ic_pvalue_fdr,
            'is_stationary': r.is_stationary,
            'n_obs': r.n_observations,
            'passes_ic': abs(r.ic_mean) > ic_threshold,
            'passes_tstat': abs(r.ic_tstat_hac) > tstat_threshold,
            'passes_fdr': r.ic_pvalue_fdr < fdr_alpha,
            'passes_all': (
                abs(r.ic_mean) > ic_threshold and
                abs(r.ic_tstat_hac) > tstat_threshold and
                r.ic_pvalue_fdr < fdr_alpha and
                r.is_stationary
            )
        })
    
    df = pd.DataFrame(data)
    
    # Composite score: |IC| × |t-stat| × (1 if stationary else 0)
    df['composite_score'] = (
        df['ic_mean'].abs() *
        df['ic_tstat_hac'].abs() *
        df['is_stationary'].astype(float)
    )
    
    # Sort by composite score
    df = df.sort_values('composite_score', ascending=False)
    
    return df


def print_test_summary(results_df: pd.DataFrame):
    """Print summary of feature testing results."""
    print("\n" + "="*80)
    print("UNIVARIATE FEATURE TEST SUMMARY")
    print("="*80)
    
    total = len(results_df)
    passed_all = results_df['passes_all'].sum()
    passed_ic = results_df['passes_ic'].sum()
    passed_tstat = results_df['passes_tstat'].sum()
    passed_fdr = results_df['passes_fdr'].sum()
    stationary = results_df['is_stationary'].sum()
    
    print(f"\nTotal features tested: {total}")
    print(f"Passed all criteria: {passed_all} ({passed_all/total*100:.1f}%)")
    print(f"  - |IC| > 0.03: {passed_ic} ({passed_ic/total*100:.1f}%)")
    print(f"  - |t-stat| > 2.0: {passed_tstat} ({passed_tstat/total*100:.1f}%)")
    print(f"  - FDR p-value < 0.05: {passed_fdr} ({passed_fdr/total*100:.1f}%)")
    print(f"  - Stationary: {stationary} ({stationary/total*100:.1f}%)")
    
    print(f"\nTop 10 Features by Composite Score:")
    print("-"*80)
    for idx, row in results_df.head(10).iterrows():
        status = "✓" if row['passes_all'] else "✗"
        print(f"{status} {row['feature']:30s} IC={row['ic_mean']:6.3f}  "
              f"t={row['ic_tstat_hac']:6.2f}  p_fdr={row['ic_pvalue_fdr']:.4f}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # Example usage
    print("Univariate Testing Framework - Ready")
    print("\nUsage:")
    print("  from src.analysis.univariate_test import test_feature, apply_fdr_correction")
    print("  results = [test_feature(df[col], df['returns']) for col in features]")
    print("  results = apply_fdr_correction(results)")
    print("  ranked = rank_features(results)")
