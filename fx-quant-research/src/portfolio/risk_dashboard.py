"""
Portfolio risk analytics for multi-currency portfolios.

Provides risk metrics, correlation monitoring, marginal risk contribution,
and stress testing capabilities.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


class PortfolioRiskDashboard:
    """
    Portfolio risk analysis for FX portfolios.
    
    Calculates:
    - Rolling correlations
    - Marginal risk contributions
    - Net currency exposure
    - VaR estimates
    - Stress test scenarios
    
    Examples:
        >>> dashboard = PortfolioRiskDashboard()
        >>> corr = dashboard.rolling_correlation(returns_df, window=60)
        >>> mrc = dashboard.marginal_risk_contribution(positions, returns_df)
        >>> exposure = dashboard.net_exposure_by_currency(positions_dict)
    """
    
    def __init__(self):
        """Initialize portfolio risk dashboard."""
        pass
    
    def rolling_correlation(
        self,
        returns_df: pd.DataFrame,
        window: int = 60
    ) -> Dict[str, pd.DataFrame]:
        """
        Calculate rolling pairwise correlations.
        
        Args:
            returns_df: DataFrame with returns for multiple assets
            window: Rolling window size
            
        Returns:
            Dictionary mapping timestamp to correlation matrices
            
        Examples:
            >>> corr_ts = dashboard.rolling_correlation(returns_df, window=60)
            >>> # Access correlation at specific time
            >>> latest_corr = corr_ts[returns_df.index[-1]]
        """
        if len(returns_df.columns) < 2:
            raise ValueError("Need at least 2 assets for correlation analysis")
        
        # Rolling correlation for each pair
        rolling_corrs = {}
        
        for col1 in returns_df.columns:
            for col2 in returns_df.columns:
                if col1 < col2:  # Avoid duplicates
                    corr_series = returns_df[col1].rolling(window=window).corr(returns_df[col2])
                    rolling_corrs[f'{col1}_{col2}'] = corr_series
        
        return rolling_corrs
    
    def detect_correlation_breaks(
        self,
        corr_series: pd.Series,
        threshold: float = 0.3,
        window: int = 20
    ) -> List[pd.Timestamp]:
        """
        Detect structural breaks in correlation.
        
        Identifies timestamps where correlation shifts significantly.
        
        Args:
            corr_series: Time series of correlation values
            threshold: Minimum absolute change to flag as break
            window: Window for detecting change
            
        Returns:
            List of timestamps where breaks detected
            
        Examples:
            >>> breaks = dashboard.detect_correlation_breaks(corr_series, threshold=0.3)
            >>> print(f"Detected {len(breaks)} correlation breaks")
        """
        breaks = []
        
        # Calculate rolling change in correlation
        corr_change = corr_series.diff(window).abs()
        
        # Flag breaks
        break_mask = corr_change > threshold
        break_timestamps = corr_series.index[break_mask].tolist()
        
        return break_timestamps
    
    def marginal_risk_contribution(
        self,
        positions: pd.Series,
        returns_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate marginal contribution to portfolio risk.
        
        MRC_i = (Σ @ w)_i / σ_portfolio
        
        Args:
            positions: Series with position weights
            returns_df: DataFrame with returns for each asset
            
        Returns:
            Series with marginal risk contribution for each asset
            
        Examples:
            >>> mrc = dashboard.marginal_risk_contribution(positions, returns_df)
            >>> print("Asset with highest risk contribution:", mrc.idxmax())
        """
        # Align positions with returns
        common_assets = positions.index.intersection(returns_df.columns)
        
        if len(common_assets) == 0:
            raise ValueError("No common assets between positions and returns")
        
        weights = positions[common_assets].values
        returns_subset = returns_df[common_assets]
        
        # Calculate covariance matrix
        cov_matrix = returns_subset.cov().values
        
        # Portfolio variance
        portfolio_var = weights @ cov_matrix @ weights
        portfolio_std = np.sqrt(portfolio_var) if portfolio_var > 0 else 0.0
        
        # Marginal risk contribution
        if portfolio_std > 0:
            mrc = (cov_matrix @ weights) / portfolio_std
        else:
            mrc = np.zeros_like(weights)
        
        return pd.Series(mrc, index=common_assets, name='marginal_risk_contribution')
    
    def net_exposure_by_currency(
        self,
        positions: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate net exposure by currency.
        
        Decomposes FX pair positions into base and quote currency exposures.
        
        Args:
            positions: Dictionary mapping pair names to position sizes
                      e.g., {'EURUSD': 100000, 'USDJPY': -50000}
            
        Returns:
            Dictionary with net exposure per currency
            
        Examples:
            >>> positions = {'EURUSD': 100000, 'GBPUSD': 50000, 'USDJPY': -75000}
            >>> exposure = dashboard.net_exposure_by_currency(positions)
            >>> print(f"USD exposure: {exposure['USD']}")
        """
        exposure = {}
        
        for pair, position in positions.items():
            if len(pair) == 6:  # Standard format like EURUSD
                base_ccy = pair[:3]
                quote_ccy = pair[3:]
                
                # Long pair = long base, short quote
                exposure[base_ccy] = exposure.get(base_ccy, 0.0) + position
                exposure[quote_ccy] = exposure.get(quote_ccy, 0.0) - position
        
        return exposure
    
    def calculate_var(
        self,
        returns: pd.Series,
        confidence_levels: List[float] = [0.95, 0.99],
        method: str = 'historical'
    ) -> Dict[str, float]:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Series of portfolio returns
            confidence_levels: List of confidence levels (e.g., [0.95, 0.99])
            method: 'historical' or 'parametric'
            
        Returns:
            Dictionary mapping confidence level to VaR estimate
            
        Examples:
            >>> var_estimates = dashboard.calculate_var(portfolio_returns)
            >>> print(f"95% VaR: {var_estimates[0.95]:.2%}")
        """
        var_dict = {}
        
        if method == 'historical':
            for conf in confidence_levels:
                var_dict[conf] = float(np.percentile(returns, (1 - conf) * 100))
        
        elif method == 'parametric':
            mean = returns.mean()
            std = returns.std()
            
            for conf in confidence_levels:
                z_score = stats.norm.ppf(1 - conf)
                var_dict[conf] = float(mean + z_score * std)
        
        else:
            raise ValueError(f"Unknown method: {method}. Use 'historical' or 'parametric'")
        
        return var_dict
    
    def stress_test(
        self,
        positions: pd.Series,
        scenarios: Dict[str, Dict[str, float]]
    ) -> pd.DataFrame:
        """
        Run stress test scenarios on portfolio.
        
        Args:
            positions: Series with current positions
            scenarios: Dict mapping scenario name to asset return shocks
                      e.g., {'2008_crisis': {'EURUSD': -0.15, 'USDJPY': 0.08}}
            
        Returns:
            DataFrame with scenario impacts
            
        Examples:
            >>> scenarios = {
            ...     '2008_Crisis': {'EURUSD': -0.15, 'GBPUSD': -0.12},
            ...     'Flash_Crash': {'EURUSD': -0.05, 'GBPUSD': -0.08}
            ... }
            >>> stress_results = dashboard.stress_test(positions, scenarios)
            >>> print(stress_results)
        """
        results = []
        
        for scenario_name, shocks in scenarios.items():
            portfolio_impact = 0.0
            
            for asset, shock in shocks.items():
                if asset in positions.index:
                    position = positions[asset]
                    impact = position * shock
                    portfolio_impact += impact
            
            results.append({
                'scenario': scenario_name,
                'portfolio_impact': portfolio_impact,
                'portfolio_impact_pct': portfolio_impact / positions.sum() if positions.sum() != 0 else 0.0
            })
        
        return pd.DataFrame(results).set_index('scenario')
    
    def calculate_portfolio_volatility(
        self,
        positions: pd.Series,
        returns_df: pd.DataFrame,
        window: int = 60
    ) -> pd.Series:
        """
        Calculate rolling portfolio volatility.
        
        Args:
            positions: Position weights (can be time-varying)
            returns_df: DataFrame with asset returns
            window: Rolling window
            
        Returns:
            Series with portfolio volatility over time
            
        Examples:
            >>> port_vol = dashboard.calculate_portfolio_volatility(positions, returns_df)
            >>> print(f"Current portfolio volatility: {port_vol.iloc[-1]:.2%}")
        """
        # Align positions and returns
        common_assets = positions.index.intersection(returns_df.columns)
        weights = positions[common_assets].values
        returns_subset = returns_df[common_assets]
        
        # Calculate portfolio returns
        portfolio_returns = (returns_subset * weights).sum(axis=1)
        
        # Rolling volatility
        portfolio_vol = portfolio_returns.rolling(window=window).std() * np.sqrt(252)
        
        return portfolio_vol


def calculate_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate correlation matrix for multiple assets.
    
    Args:
        returns_df: DataFrame with returns for multiple assets
        
    Returns:
        Correlation matrix
        
    Examples:
        >>> corr_matrix = calculate_correlation_matrix(returns_df)
        >>> print(corr_matrix)
    """
    return returns_df.corr()


def portfolio_diversification_ratio(
    positions: pd.Series,
    returns_df: pd.DataFrame
) -> float:
    """
    Calculate portfolio diversification ratio.
    
    Ratio of weighted average volatility to portfolio volatility.
    Higher values indicate better diversification.
    
    Args:
        positions: Position weights
        returns_df: DataFrame with asset returns
        
    Returns:
        Diversification ratio
        
    Examples:
        >>> div_ratio = portfolio_diversification_ratio(positions, returns_df)
        >>> print(f"Diversification ratio: {div_ratio:.2f}")
    """
    common_assets = positions.index.intersection(returns_df.columns)
    weights = positions[common_assets].values
    returns_subset = returns_df[common_assets]
    
    # Individual volatilities
    asset_vols = returns_subset.std().values
    
    # Weighted average volatility
    weighted_avg_vol = np.sum(np.abs(weights) * asset_vols)
    
    # Portfolio volatility
    cov_matrix = returns_subset.cov().values
    portfolio_var = weights @ cov_matrix @ weights
    portfolio_vol = np.sqrt(portfolio_var) if portfolio_var > 0 else 0.0
    
    # Diversification ratio
    if portfolio_vol > 0:
        div_ratio = weighted_avg_vol / portfolio_vol
    else:
        div_ratio = 1.0
    
    return float(div_ratio)


def plot_correlation_heatmap(
    returns_df: pd.DataFrame,
    title: str = "Correlation Heatmap",
    figsize: tuple = (8, 6)
):
    """
    Plot correlation heatmap for a set of return series.

    Args:
        returns_df: DataFrame of returns (columns = assets)
        title: Plot title
        figsize: Figure size

    Returns:
        Matplotlib Axes for further customization.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    corr = returns_df.corr()
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(corr, annot=True, cmap="RdBu_r", center=0, ax=ax)
    ax.set_title(title)
    plt.tight_layout()
    return ax


def plot_currency_exposure_heatmap(
    positions: Dict[str, float],
    title: str = "Net Currency Exposure",
    figsize: tuple = (6, 4)
):
    """
    Visualize net currency exposure as a heatmap.

    Args:
        positions: Dict of pair->notional
        title: Plot title
        figsize: Figure size
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    exposure = PortfolioRiskDashboard().net_exposure_by_currency(positions)
    exposure_series = pd.Series(exposure).sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(
        exposure_series.to_frame("exposure").T,
        annot=True,
        cmap="YlGnBu",
        fmt=".0f",
        ax=ax
    )
    ax.set_title(title)
    plt.tight_layout()
    return ax
