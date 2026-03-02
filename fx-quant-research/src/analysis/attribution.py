"""
Performance attribution and decomposition.

Provides alpha/beta decomposition, cost attribution, and Monte Carlo
significance testing for strategy performance.
"""

from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


class PerformanceAttribution:
    """
    Comprehensive performance attribution analysis.
    
    Decomposes returns into:
    - Alpha (skill-based returns)
    - Beta (factor exposures)
    - Cost attribution (spread, slippage, etc.)
    - Luck assessment (Monte Carlo p-value)
    
    Examples:
        >>> attribution = PerformanceAttribution()
        >>> alpha_beta = attribution.alpha_beta_decomposition(
        ...     strategy_returns, factors_df
        ... )
        >>> print(f"Alpha: {alpha_beta['alpha']:.4f}")
        >>> print(f"Alpha t-stat: {alpha_beta['alpha_tstat']:.2f}")
    """
    
    def __init__(self):
        """Initialize performance attribution."""
        pass
    
    def alpha_beta_decomposition(
        self,
        strategy_returns: pd.Series,
        factors: pd.DataFrame
    ) -> Dict[str, any]:
        """
        Decompose returns into alpha and factor betas using OLS regression.
        
        Model: strategy_returns = alpha + Σ(beta_i * factor_i) + epsilon
        
        Args:
            strategy_returns: Series of strategy returns
            factors: DataFrame with factor returns (e.g., carry, momentum, value)
            
        Returns:
            Dictionary with alpha, betas, t-statistics, and R-squared
            
        Examples:
            >>> factors = pd.DataFrame({
            ...     'carry': carry_factor_returns,
            ...     'momentum': momentum_factor_returns
            ... })
            >>> result = attribution.alpha_beta_decomposition(strat_returns, factors)
            >>> print(f"Alpha: {result['alpha']:.6f} (t={result['alpha_tstat']:.2f})")
            >>> print(f"Carry beta: {result['betas']['carry']:.3f}")
        """
        # Align indices
        common_index = strategy_returns.index.intersection(factors.index)
        y = strategy_returns.loc[common_index]
        X = factors.loc[common_index]
        
        # Add constant for alpha
        X_with_const = sm.add_constant(X)
        
        # Run OLS regression
        model = sm.OLS(y, X_with_const).fit()
        
        # Extract results
        alpha = float(model.params['const'])
        alpha_tstat = float(model.tvalues['const'])
        alpha_pval = float(model.pvalues['const'])
        
        betas = {
            col: float(model.params[col])
            for col in factors.columns
        }
        
        beta_tstats = {
            col: float(model.tvalues[col])
            for col in factors.columns
        }
        
        return {
            'alpha': alpha,
            'alpha_tstat': alpha_tstat,
            'alpha_pvalue': alpha_pval,
            'betas': betas,
            'beta_tstats': beta_tstats,
            'r_squared': float(model.rsquared),
            'adj_r_squared': float(model.rsquared_adj),
            'residuals': model.resid
        }
    
    def cost_attribution(
        self,
        gross_returns: pd.Series,
        net_returns: pd.Series,
        cost_breakdown: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Attribute performance loss to different cost components.
        
        Args:
            gross_returns: Returns before costs
            net_returns: Returns after costs
            cost_breakdown: Optional DataFrame with cost components
            
        Returns:
            Dictionary with cost attribution
            
        Examples:
            >>> costs = attribution.cost_attribution(gross_returns, net_returns, cost_df)
            >>> print(f"Total cost drag: {costs['total_cost_bps']:.2f} bps")
            >>> print(f"Spread costs: {costs.get('spread_cost_bps', 0):.2f} bps")
        """
        # Total cost impact
        total_cost = (gross_returns - net_returns).sum()
        
        # Annualize
        annualized_gross = gross_returns.mean() * 252
        annualized_net = net_returns.mean() * 252
        annualized_cost = annualized_gross - annualized_net
        
        result = {
            'total_cost': float(total_cost),
            'total_cost_bps': float(total_cost * 10000),
            'annualized_cost': float(annualized_cost),
            'annualized_cost_bps': float(annualized_cost * 10000),
            'cost_pct_of_gross': float(total_cost / gross_returns.sum() * 100) if gross_returns.sum() != 0 else 0.0
        }
        
        # Break down by component if available
        if cost_breakdown is not None and len(cost_breakdown) > 0:
            for component in ['spread', 'slippage', 'impact', 'swap']:
                if component in cost_breakdown.columns:
                    component_cost = cost_breakdown[component].sum()
                    result[f'{component}_cost'] = float(component_cost)
                    result[f'{component}_cost_bps'] = float(component_cost * 10000)
        
        return result
    
    def monte_carlo_pvalue(
        self,
        strategy_sharpe: float,
        returns: pd.Series,
        n_simulations: int = 10000,
        random_state: int = 42
    ) -> Dict[str, any]:
        """
        Calculate Monte Carlo p-value for strategy Sharpe ratio.
        
        Tests null hypothesis: strategy is luck (random permutation of returns).
        
        Args:
            strategy_sharpe: Actual strategy Sharpe ratio
            returns: Strategy returns for bootstrap sampling
            n_simulations: Number of random strategies to generate
            random_state: Random seed
            
        Returns:
            Dictionary with p-value and distribution statistics
            
        Examples:
            >>> mc_result = attribution.monte_carlo_pvalue(
            ...     strategy_sharpe=1.5,
            ...     returns=strategy_returns,
            ...     n_simulations=10000
            ... )
            >>> print(f"p-value: {mc_result['p_value']:.4f}")
            >>> if mc_result['p_value'] < 0.05:
            ...     print("Strategy is statistically significant!")
        """
        rng = np.random.RandomState(random_state)
        
        # Generate random strategies by permuting returns
        random_sharpes = []
        
        returns_array = returns.dropna().values
        n_returns = len(returns_array)
        
        for _ in range(n_simulations):
            # Random permutation
            random_returns = rng.choice(returns_array, size=n_returns, replace=True)
            
            # Calculate Sharpe
            mean_ret = random_returns.mean()
            std_ret = random_returns.std()
            
            if std_ret > 0:
                random_sharpe = (mean_ret / std_ret) * np.sqrt(252)
            else:
                random_sharpe = 0.0
            
            random_sharpes.append(random_sharpe)
        
        random_sharpes = np.array(random_sharpes)
        
        # Calculate p-value (one-tailed: how many random >= actual)
        p_value = (random_sharpes >= strategy_sharpe).mean()
        
        # Percentile rank
        percentile = stats.percentileofscore(random_sharpes, strategy_sharpe)
        
        return {
            'p_value': float(p_value),
            'percentile_rank': float(percentile),
            'random_sharpe_mean': float(random_sharpes.mean()),
            'random_sharpe_std': float(random_sharpes.std()),
            'random_sharpe_95th': float(np.percentile(random_sharpes, 95)),
            'random_sharpe_99th': float(np.percentile(random_sharpes, 99)),
            'n_simulations': n_simulations,
            'is_significant_5pct': p_value < 0.05,
            'is_significant_1pct': p_value < 0.01
        }
    
    def information_ratio(
        self,
        active_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """
        Calculate information ratio.
        
        IR = mean(active_returns) / std(active_returns)
        where active_returns = strategy_returns - benchmark_returns
        
        Args:
            active_returns: Strategy returns
            benchmark_returns: Benchmark returns
            
        Returns:
            Annualized information ratio
            
        Examples:
            >>> ir = attribution.information_ratio(strategy_returns, benchmark_returns)
            >>> print(f"Information Ratio: {ir:.2f}")
        """
        # Calculate active returns
        common_index = active_returns.index.intersection(benchmark_returns.index)
        active = active_returns.loc[common_index] - benchmark_returns.loc[common_index]
        
        # Information ratio
        if active.std() > 0:
            ir = (active.mean() / active.std()) * np.sqrt(252)
        else:
            ir = 0.0
        
        return float(ir)
    
    def attribution_report(
        self,
        strategy_returns: pd.Series,
        gross_returns: Optional[pd.Series] = None,
        factors: Optional[pd.DataFrame] = None,
        cost_breakdown: Optional[pd.DataFrame] = None
    ) -> Dict[str, any]:
        """
        Generate comprehensive attribution report.
        
        Args:
            strategy_returns: Net strategy returns
            gross_returns: Optional gross returns (before costs)
            factors: Optional factor returns for alpha/beta decomposition
            cost_breakdown: Optional cost breakdown
            
        Returns:
            Comprehensive attribution dictionary
            
        Examples:
            >>> report = attribution.attribution_report(
            ...     strategy_returns=net_returns,
            ...     gross_returns=gross_returns,
            ...     factors=factors_df,
            ...     cost_breakdown=costs_df
            ... )
            >>> print(json.dumps(report, indent=2))
        """
        report = {}
        
        # Basic statistics
        sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252) if strategy_returns.std() > 0 else 0.0
        report['sharpe_ratio'] = float(sharpe)
        report['mean_return'] = float(strategy_returns.mean())
        report['std_return'] = float(strategy_returns.std())
        
        # Alpha/Beta decomposition
        if factors is not None:
            try:
                alpha_beta = self.alpha_beta_decomposition(strategy_returns, factors)
                report['alpha_beta'] = alpha_beta
            except Exception as e:
                report['alpha_beta'] = {'error': str(e)}
        
        # Cost attribution
        if gross_returns is not None:
            try:
                costs = self.cost_attribution(gross_returns, strategy_returns, cost_breakdown)
                report['costs'] = costs
            except Exception as e:
                report['costs'] = {'error': str(e)}
        
        # Monte Carlo p-value
        try:
            mc_result = self.monte_carlo_pvalue(sharpe, strategy_returns)
            report['monte_carlo'] = mc_result
        except Exception as e:
            report['monte_carlo'] = {'error': str(e)}
        
        return report
