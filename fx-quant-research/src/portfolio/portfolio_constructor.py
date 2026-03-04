"""
Portfolio construction and risk management.

Implements:
- Cross-pair correlation analysis
- Risk parity position sizing
- Portfolio diversification metrics
- Correlation-based portfolio optimization
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from pathlib import Path


class PortfolioConstructor:
    """
    Multi-currency portfolio construction with correlation analysis.
    
    Features:
    - Correlation matrix calculation
    - Risk parity weighting
    - Equal weight vs optimal weight comparison
    - Portfolio diversification ratio
    
    Examples:
        >>> pc = PortfolioConstructor()
        >>> weights = pc.calculate_risk_parity_weights(returns_df)
        >>> corr_matrix = pc.calculate_correlation_matrix(returns_df)
    """
    
    def __init__(
        self,
        correlation_window: int = 60,
        min_correlation_threshold: float = 0.7
    ):
        """
        Initialize portfolio constructor.
        
        Args:
            correlation_window: Rolling window for correlation (default 60 days)
            min_correlation_threshold: Warn if correlations above this (default 0.7)
        """
        self.correlation_window = correlation_window
        self.min_correlation_threshold = min_correlation_threshold
    
    def calculate_correlation_matrix(
        self,
        returns_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix of returns.
        
        Args:
            returns_df: DataFrame with returns for each pair (columns = pairs)
            
        Returns:
            Correlation matrix
        """
        return returns_df.corr()
    
    def calculate_rolling_correlation(
        self,
        returns_df: pd.DataFrame,
        pair1: str,
        pair2: str
    ) -> pd.Series:
        """
        Calculate rolling correlation between two pairs.
        
        Args:
            returns_df: DataFrame with returns
            pair1: First currency pair
            pair2: Second currency pair
            
        Returns:
            Series of rolling correlations
        """
        return returns_df[pair1].rolling(
            window=self.correlation_window,
            min_periods=self.correlation_window // 2
        ).corr(returns_df[pair2])
    
    def calculate_risk_parity_weights(
        self,
        returns_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate risk parity weights (inverse volatility weighting).
        
        Args:
            returns_df: DataFrame with returns for each pair
            
        Returns:
            Dict of {pair: weight}
        """
        # Calculate volatilities
        vols = returns_df.std()
        
        # Inverse volatility
        inv_vols = 1 / vols
        
        # Normalize to sum to 1
        weights = inv_vols / inv_vols.sum()
        
        return weights.to_dict()
    
    def calculate_minimum_variance_weights(
        self,
        returns_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate minimum variance portfolio weights.
        
        Args:
            returns_df: DataFrame with returns
            
        Returns:
            Dict of {pair: weight}
        """
        # Covariance matrix
        cov_matrix = returns_df.cov()
        
        # Number of assets
        n = len(returns_df.columns)
        
        # Objective: minimize portfolio variance
        def portfolio_variance(weights):
            return weights.T @ cov_matrix.values @ weights
        
        # Constraints: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        # Bounds: weights between 0 and 1 (long only)
        bounds = tuple((0, 1) for _ in range(n))
        
        # Initial guess: equal weight
        x0 = np.array([1/n] * n)
        
        # Optimize
        result = minimize(
            portfolio_variance,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            weights = dict(zip(returns_df.columns, result.x))
            return weights
        else:
            # Fallback to equal weight
            return {pair: 1/n for pair in returns_df.columns}
    
    def calculate_diversification_ratio(
        self,
        returns_df: pd.DataFrame,
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate portfolio diversification ratio.
        
        DR = (weighted average of individual vols) / (portfolio vol)
        DR > 1 indicates diversification benefit
        
        Args:
            returns_df: DataFrame with returns
            weights: Dict of portfolio weights
            
        Returns:
            Diversification ratio
        """
        # Individual volatilities
        vols = returns_df.std()
        
        # Weighted average volatility
        weighted_avg_vol = sum(weights[pair] * vols[pair] for pair in weights)
        
        # Portfolio returns
        portfolio_returns = sum(returns_df[pair] * weights[pair] for pair in weights)
        
        # Portfolio volatility
        portfolio_vol = portfolio_returns.std()
        
        # Diversification ratio
        dr = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1.0
        
        return dr
    
    def identify_clusters(
        self,
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7
    ) -> Dict[int, List[str]]:
        """
        Identify highly correlated pair clusters.
        
        Args:
            correlation_matrix: Correlation matrix
            threshold: Correlation threshold for same cluster
            
        Returns:
            Dict of {cluster_id: [pairs]}
        """
        from sklearn.cluster import AgglomerativeClustering
        
        # Convert correlation to distance (1 - |corr|)
        distance_matrix = 1 - np.abs(correlation_matrix.values)
        
        # Hierarchical clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            linkage='average',
            metric='precomputed'
        )
        
        labels = clustering.fit_predict(distance_matrix)
        
        # Group pairs by cluster
        clusters = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(correlation_matrix.columns[idx])
        
        return clusters
    
    def generate_portfolio_report(
        self,
        returns_df: pd.DataFrame,
        equal_weight: bool = True,
        risk_parity: bool = True,
        min_variance: bool = True
    ) -> Dict:
        """
        Generate comprehensive portfolio analysis report.
        
        Args:
            returns_df: DataFrame with returns for each pair
            equal_weight: Include equal weight portfolio
            risk_parity: Include risk parity portfolio
            min_variance: Include minimum variance portfolio
            
        Returns:
            Dict with portfolio statistics
        """
        report = {}
        
        n = len(returns_df.columns)
        
        # Correlation analysis
        corr_matrix = self.calculate_correlation_matrix(returns_df)
        report['correlation_matrix'] = corr_matrix
        
        # Average correlation
        corr_values = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]
        report['avg_correlation'] = corr_values.mean()
        report['max_correlation'] = corr_values.max()
        report['min_correlation'] = corr_values.min()
        
        # High correlation pairs
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr_val = corr_matrix.iloc[i, j]
                if abs(corr_val) > self.min_correlation_threshold:
                    high_corr_pairs.append((
                        corr_matrix.columns[i],
                        corr_matrix.columns[j],
                        corr_val
                    ))
        report['high_correlation_pairs'] = high_corr_pairs
        
        # Portfolio strategies
        portfolios = {}
        
        if equal_weight:
            ew_weights = {pair: 1/n for pair in returns_df.columns}
            ew_returns = sum(returns_df[pair] * ew_weights[pair] for pair in returns_df.columns)
            
            portfolios['equal_weight'] = {
                'weights': ew_weights,
                'returns': ew_returns,
                'sharpe': ew_returns.mean() / ew_returns.std() * np.sqrt(252) if ew_returns.std() > 0 else 0,
                'volatility': ew_returns.std() * np.sqrt(252),
                'diversification_ratio': self.calculate_diversification_ratio(returns_df, ew_weights)
            }
        
        if risk_parity:
            rp_weights = self.calculate_risk_parity_weights(returns_df)
            rp_returns = sum(returns_df[pair] * rp_weights[pair] for pair in returns_df.columns)
            
            portfolios['risk_parity'] = {
                'weights': rp_weights,
                'returns': rp_returns,
                'sharpe': rp_returns.mean() / rp_returns.std() * np.sqrt(252) if rp_returns.std() > 0 else 0,
                'volatility': rp_returns.std() * np.sqrt(252),
                'diversification_ratio': self.calculate_diversification_ratio(returns_df, rp_weights)
            }
        
        if min_variance:
            mv_weights = self.calculate_minimum_variance_weights(returns_df)
            mv_returns = sum(returns_df[pair] * mv_weights[pair] for pair in returns_df.columns)
            
            portfolios['min_variance'] = {
                'weights': mv_weights,
                'returns': mv_returns,
                'sharpe': mv_returns.mean() / mv_returns.std() * np.sqrt(252) if mv_returns.std() > 0 else 0,
                'volatility': mv_returns.std() * np.sqrt(252),
                'diversification_ratio': self.calculate_diversification_ratio(returns_df, mv_weights)
            }
        
        report['portfolios'] = portfolios
        
        return report


if __name__ == "__main__":
    print("Portfolio construction module loaded.")
    print("Usage:")
    print("  from src.portfolio.portfolio_constructor import PortfolioConstructor")
    print("  pc = PortfolioConstructor()")
    print("  report = pc.generate_portfolio_report(returns_df)")
