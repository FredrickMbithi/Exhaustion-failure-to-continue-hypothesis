"""
Monte Carlo validation and robustness testing.

Implements:
- Bootstrap resampling of trade returns
- Synthetic equity curve generation
- Drawdown probability estimation
- Overfitting assessment
- Statistical significance testing
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from pathlib import Path
import warnings


class MonteCarloValidator:
    """
    Monte Carlo simulation for strategy validation.
    
    Methods:
    - Bootstrap trade returns to assess variability
    - Generate synthetic equity curves
    - Calculate drawdown probabilities
    - Test statistical significance of edge
    
    Examples:
        >>> mc = MonteCarloValidator(n_simulations=1000)
        >>> results = mc.bootstrap_trades(trade_returns)
        >>> prob_profitable = mc.calculate_profitability_probability(results)
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        random_state: int = 42
    ):
        """
        Initialize Monte Carlo validator.
        
        Args:
            n_simulations: Number of simulation paths (default 1000)
            random_state: Random seed for reproducibility
        """
        self.n_simulations = n_simulations
        self.random_state = random_state
        np.random.seed(random_state)
    
    def bootstrap_trade_returns(
        self,
        trade_returns: pd.Series
    ) -> pd.DataFrame:
        """
        Bootstrap trade returns to generate simulated equity curves.
        
        Args:
            trade_returns: Series of individual trade returns (NOT daily returns)
            
        Returns:
            DataFrame with simulated cumulative returns (n_simulations columns)
        """
        n_trades = len(trade_returns)
        
        # Generate bootstrap samples
        simulations = {}
        
        for i in range(self.n_simulations):
            # Resample with replacement
            bootstrap_sample = np.random.choice(
                trade_returns.values,
                size=n_trades,
                replace=True
            )
            
            # Calculate cumulative returns
            cumulative_returns = (1 + pd.Series(bootstrap_sample)).cumprod() - 1
            simulations[f'sim_{i}'] = cumulative_returns.values
        
        return pd.DataFrame(simulations)
    
    def calculate_profitability_probability(
        self,
        simulated_curves: pd.DataFrame
    ) -> float:
        """
        Calculate probability that strategy is profitable.
        
        Args:
            simulated_curves: DataFrame of simulated equity curves
            
        Returns:
            Probability (0-1) that final return > 0
        """
        final_returns = simulated_curves.iloc[-1]
        prob_profitable = (final_returns > 0).mean()
        
        return prob_profitable
    
    def calculate_drawdown_distribution(
        self,
        simulated_curves: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate drawdown statistics across simulations.
        
        Args:
            simulated_curves: DataFrame of simulated equity curves
            
        Returns:
            Dict with drawdown percentiles
        """
        max_drawdowns = []
        
        for col in simulated_curves.columns:
            equity = 1 + simulated_curves[col]
            running_max = equity.expanding().max()
            drawdown = (equity - running_max) / running_max
            max_drawdown = drawdown.min()
            max_drawdowns.append(max_drawdown)
        
        max_drawdowns = np.array(max_drawdowns)
        
        return {
            'mean': max_drawdowns.mean(),
            'median': np.median(max_drawdowns),
            'p5': np.percentile(max_drawdowns, 5),
            'p25': np.percentile(max_drawdowns, 25),
            'p75': np.percentile(max_drawdowns, 75),
            'p95': np.percentile(max_drawdowns, 95),
            'worst': max_drawdowns.min()
        }
    
    def calculate_sharpe_distribution(
        self,
        simulated_curves: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate Sharpe ratio distribution across simulations.
        
        Args:
            simulated_curves: DataFrame of simulated equity curves
            
        Returns:
            Dict with Sharpe percentiles
        """
        sharpe_ratios = []
        
        for col in simulated_curves.columns:
            returns = simulated_curves[col].diff().dropna()
            if returns.std() > 0:
                sharpe = returns.mean() / returns.std() * np.sqrt(252)
                sharpe_ratios.append(sharpe)
        
        sharpe_ratios = np.array(sharpe_ratios)
        
        return {
            'mean': sharpe_ratios.mean(),
            'median': np.median(sharpe_ratios),
            'p5': np.percentile(sharpe_ratios, 5),
            'p25': np.percentile(sharpe_ratios, 25),
            'p75': np.percentile(sharpe_ratios, 75),
            'p95': np.percentile(sharpe_ratios, 95),
            'best': sharpe_ratios.max(),
            'worst': sharpe_ratios.min()
        }
    
    def permutation_test(
        self,
        signals: pd.Series,
        returns: pd.Series,
        n_permutations: int = 1000
    ) -> float:
        """
        Permutation test to assess if IC is statistically significant.
        
        Randomly permutes returns to test if observed IC is due to chance.
        
        Args:
            signals: Strategy signals (-1, 0, 1)
            returns: Actual forward returns
            n_permutations: Number of permutations
            
        Returns:
            p-value (probability observed IC due to chance)
        """
        # Calculate observed IC
        valid = pd.DataFrame({
            'signal': signals,
            'returns': returns
        }).dropna()
        
        valid = valid[valid['signal'] != 0]
        
        if len(valid) < 10:
            warnings.warn("Too few signals for permutation test")
            return 1.0
        
        from scipy.stats import spearmanr
        observed_ic, _ = spearmanr(valid['signal'], valid['returns'])
        
        # Permutation distribution
        permuted_ics = []
        
        for _ in range(n_permutations):
            permuted_returns = np.random.permutation(valid['returns'].values)
            permuted_ic, _ = spearmanr(valid['signal'], permuted_returns)
            permuted_ics.append(permuted_ic)
        
        permuted_ics = np.array(permuted_ics)
        
        # Two-tailed p-value
        p_value = (np.abs(permuted_ics) >= np.abs(observed_ic)).mean()
        
        return p_value
    
    def block_bootstrap(
        self,
        trade_returns: pd.Series,
        block_size: int = 5
    ) -> pd.DataFrame:
        """
        Block bootstrap for time-series dependencies.
        
        Preserves short-term autocorrelation by resampling blocks.
        
        Args:
            trade_returns: Series of trade returns
            block_size: Size of resampling blocks
            
        Returns:
            DataFrame of simulated curves
        """
        n_trades = len(trade_returns)
        n_blocks = int(np.ceil(n_trades / block_size))
        
        simulations = {}
        
        for i in range(self.n_simulations):
            # Create blocks
            blocks = []
            for j in range(0, n_trades, block_size):
                blocks.append(trade_returns.iloc[j:j+block_size])
            
            # Resample blocks
            sampled_blocks = [blocks[idx] for idx in np.random.choice(len(blocks), n_blocks, replace=True)]
            
            # Concatenate and trim to original length
            bootstrap_sample = pd.concat(sampled_blocks).iloc[:n_trades]
            
            # Calculate cumulative returns
            cumulative_returns = (1 + bootstrap_sample).cumprod() - 1
            simulations[f'sim_{i}'] = cumulative_returns.values
        
        return pd.DataFrame(simulations)
    
    def generate_validation_report(
        self,
        trade_returns: pd.Series,
        signals: Optional[pd.Series] = None,
        returns: Optional[pd.Series] = None,
        use_block_bootstrap: bool = False,
        block_size: int = 5
    ) -> Dict:
        """
        Generate comprehensive validation report.
        
        Args:
            trade_returns: Series of individual trade returns
            signals: Optional strategy signals for permutation test
            returns: Optional actual returns for permutation test
            use_block_bootstrap: Use block bootstrap for time dependencies
            block_size: Block size for block bootstrap
            
        Returns:
            Dict with validation statistics
        """
        report = {}
        
        # Observed statistics
        report['observed'] = {
            'n_trades': len(trade_returns),
            'mean_return': trade_returns.mean(),
            'win_rate': (trade_returns > 0).mean(),
            'total_return': (1 + trade_returns).prod() - 1,
            'volatility': trade_returns.std(),
            'sharpe': trade_returns.mean() / trade_returns.std() * np.sqrt(252) if trade_returns.std() > 0 else 0
        }
        
        # Bootstrap simulations
        if use_block_bootstrap:
            simulated_curves = self.block_bootstrap(trade_returns, block_size)
        else:
            simulated_curves = self.bootstrap_trade_returns(trade_returns)
        
        report['n_simulations'] = self.n_simulations
        
        # Profitability probability
        report['prob_profitable'] = self.calculate_profitability_probability(simulated_curves)
        
        # Drawdown distribution
        report['drawdown_distribution'] = self.calculate_drawdown_distribution(simulated_curves)
        
        # Sharpe distribution
        report['sharpe_distribution'] = self.calculate_sharpe_distribution(simulated_curves)
        
        # Return distribution
        final_returns = simulated_curves.iloc[-1]
        report['return_distribution'] = {
            'mean': final_returns.mean(),
            'median': final_returns.median(),
            'p5': final_returns.quantile(0.05),
            'p25': final_returns.quantile(0.25),
            'p75': final_returns.quantile(0.75),
            'p95': final_returns.quantile(0.95)
        }
        
        # Permutation test (if signals provided)
        if signals is not None and returns is not None:
            report['permutation_test_pval'] = self.permutation_test(signals, returns)
        
        return report
    
    def plot_simulation_distribution(
        self,
        simulated_curves: pd.DataFrame,
        observed_curve: Optional[pd.Series] = None,
        percentiles: List[int] = [5, 25, 50, 75, 95]
    ) -> pd.DataFrame:
        """
        Generate percentile bands for plotting.
        
        Args:
            simulated_curves: DataFrame of simulated equity curves
            observed_curve: Optional observed equity curve to compare
            percentiles: Percentiles to calculate
            
        Returns:
            DataFrame with percentile values at each point
        """
        percentile_data = {}
        
        for p in percentiles:
            percentile_data[f'p{p}'] = simulated_curves.quantile(p/100, axis=1)
        
        result = pd.DataFrame(percentile_data)
        
        if observed_curve is not None:
            result['observed'] = observed_curve.values
        
        return result


if __name__ == "__main__":
    print("Monte Carlo validation module loaded.")
    print("Usage:")
    print("  from src.analysis.monte_carlo import MonteCarloValidator")
    print("  mc = MonteCarloValidator(n_simulations=1000)")
    print("  report = mc.generate_validation_report(trade_returns)")
