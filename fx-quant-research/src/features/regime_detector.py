"""
Regime detection using Hidden Markov Models.

Implements HMM-based regime detection for identifying market states
(e.g., low/medium/high volatility) with comprehensive analysis.
"""

from typing import Dict, Optional, List

import numpy as np
import pandas as pd
from hmmlearn import hmm
from sklearn.mixture import GaussianMixture


class RegimeDetector:
    """
    Hidden Markov Model for regime detection.
    
    Uses hmmlearn for temporal regime classification.
    Fallback to GMM if temporal structure not needed.
    
    Examples:
        >>> detector = RegimeDetector(n_states=3, random_state=42)
        >>> detector.fit(features_df)
        >>> states = detector.predict(features_df)
        >>> probs = detector.predict_proba(features_df)
    """
    
    def __init__(
        self,
        n_states: int = 3,
        covariance_type: str = 'full',
        max_iter: int = 100,
        random_state: int = 42
    ):
        """
        Initialize regime detector.
        
        Args:
            n_states: Number of hidden states (regimes)
            covariance_type: 'full', 'diag', 'tied', or 'spherical'
            max_iter: Maximum EM iterations
            random_state: Random seed for reproducibility
        """
        self.n_states = n_states
        self.covariance_type = covariance_type
        self.max_iter = max_iter
        self.random_state = random_state
        
        # Initialize HMM
        self.model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type=covariance_type,
            n_iter=max_iter,
            random_state=random_state
        )
        
        self.is_fitted = False
        self.feature_names = None
    
    def fit(self, features: pd.DataFrame) -> 'RegimeDetector':
        """
        Fit HMM to feature data.
        
        Args:
            features: DataFrame with stationary features (returns, volatility, etc.)
                     Each column should be a feature, must be stationary
            
        Returns:
            Self (fitted detector)
            
        Raises:
            ValueError: If features contain NaN or insufficient data
            
        Examples:
            >>> features = pd.DataFrame({
            ...     'returns': df['returns'],
            ...     'volatility': df['volatility_20'],
            ...     'volume_zscore': df['volume_zscore']
            ... }).dropna()
            >>> detector.fit(features)
        """
        if features.isnull().any().any():
            raise ValueError("Features contain NaN values. Clean data before fitting.")
        
        if len(features) < self.n_states * 10:
            raise ValueError(
                f"Need at least {self.n_states * 10} samples for {self.n_states} states. "
                f"Got {len(features)}"
            )
        
        self.feature_names = list(features.columns)
        
        # Fit HMM
        X = features.values
        self.model.fit(X)
        
        self.is_fitted = True
        
        return self
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """
        Predict hidden state sequence.
        
        Args:
            features: DataFrame with same features as used in fit()
            
        Returns:
            Series with predicted state labels (0 to n_states-1)
            
        Raises:
            ValueError: If not fitted or features mismatch
            
        Examples:
            >>> states = detector.predict(features)
            >>> print(states.value_counts())
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        if list(features.columns) != self.feature_names:
            raise ValueError(
                f"Feature mismatch. Expected {self.feature_names}, "
                f"got {list(features.columns)}"
            )
        
        X = features.values
        states = self.model.predict(X)
        
        return pd.Series(states, index=features.index, name='regime')
    
    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Predict regime probabilities.
        
        Args:
            features: DataFrame with same features as used in fit()
            
        Returns:
            DataFrame with probability for each state
            
        Examples:
            >>> probs = detector.predict_proba(features)
            >>> print(probs.head())
            >>> # prob_state_0  prob_state_1  prob_state_2
            >>> # 0.05          0.15          0.80
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        X = features.values
        probs = self.model.predict_proba(X)
        
        # Create DataFrame
        prob_df = pd.DataFrame(
            probs,
            index=features.index,
            columns=[f'prob_state_{i}' for i in range(self.n_states)]
        )
        
        return prob_df
    
    def score(self, features: pd.DataFrame) -> float:
        """
        Calculate log-likelihood of features under the model.
        
        Args:
            features: DataFrame with features
            
        Returns:
            Log-likelihood score (higher is better)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        X = features.values
        return self.model.score(X)
    
    def get_transition_matrix(self) -> np.ndarray:
        """
        Get state transition probability matrix.
        
        Returns:
            Array of shape (n_states, n_states) with transition probabilities
            
        Examples:
            >>> trans_matrix = detector.get_transition_matrix()
            >>> print("Probability of staying in state 0:", trans_matrix[0, 0])
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        return self.model.transmat_
    
    def get_state_means(self) -> Dict[int, Dict[str, float]]:
        """
        Get mean feature values for each state.
        
        Returns:
            Dictionary mapping state to feature means
            
        Examples:
            >>> means = detector.get_state_means()
            >>> print(f"State 0 mean return: {means[0]['returns']:.6f}")
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        means_dict = {}
        for state in range(self.n_states):
            means_dict[state] = {
                feat: float(self.model.means_[state, i])
                for i, feat in enumerate(self.feature_names)
            }
        
        return means_dict


def calculate_regime_stats(states: pd.Series) -> Dict[str, any]:
    """
    Calculate regime statistics.
    
    Computes:
    - Duration distribution for each state
    - Transition probability matrix
    - State frequencies
    - Stability metrics
    
    Args:
        states: Series with regime labels
        
    Returns:
        Dictionary with regime statistics
        
    Examples:
        >>> stats = calculate_regime_stats(states)
        >>> print(f"Mean duration in state 0: {stats['mean_durations'][0]:.1f} bars")
    """
    stats = {}
    
    # State frequencies
    value_counts = states.value_counts()
    stats['frequencies'] = value_counts.to_dict()
    stats['percentages'] = (value_counts / len(states) * 100).to_dict()
    
    # Calculate durations
    state_changes = states != states.shift(1)
    regime_blocks = state_changes.cumsum()
    
    durations = {}
    mean_durations = {}
    
    for state in states.unique():
        state_mask = (states == state)
        state_blocks = regime_blocks[state_mask]
        block_durations = state_blocks.value_counts()
        
        durations[int(state)] = block_durations.tolist()
        mean_durations[int(state)] = float(block_durations.mean())
    
    stats['durations'] = durations
    stats['mean_durations'] = mean_durations
    
    # Transition matrix (empirical)
    n_states = len(states.unique())
    transition_matrix = np.zeros((n_states, n_states))
    
    for i in range(len(states) - 1):
        from_state = states.iloc[i]
        to_state = states.iloc[i + 1]
        transition_matrix[from_state, to_state] += 1
    
    # Normalize
    row_sums = transition_matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    transition_matrix = transition_matrix / row_sums
    
    stats['transition_matrix'] = transition_matrix
    
    # Stability: probability of staying in same state
    stability = {
        int(state): float(transition_matrix[state, state])
        for state in range(n_states)
    }
    stats['stability'] = stability
    
    return stats


def regime_performance(
    returns: pd.Series,
    states: pd.Series,
    annualization_factor: int = 252
) -> pd.DataFrame:
    """
    Calculate strategy performance by regime.
    
    Args:
        returns: Series of strategy returns
        states: Series of regime labels
        annualization_factor: For Sharpe calculation
        
    Returns:
        DataFrame with performance metrics by regime
        
    Examples:
        >>> perf = regime_performance(returns, states)
        >>> print(perf)
        >>> #        mean_return  std_return  sharpe  count
        >>> # state                                        
        >>> # 0      0.0005       0.0080     0.99    450
        >>> # 1     -0.0002       0.0150    -0.21    320
        >>> # 2      0.0008       0.0050     2.54    230
    """
    # Align indices
    common_index = returns.index.intersection(states.index)
    returns_aligned = returns.loc[common_index]
    states_aligned = states.loc[common_index]
    
    # Group by state
    grouped = returns_aligned.groupby(states_aligned)
    
    results = []
    for state, group_returns in grouped:
        mean_ret = group_returns.mean()
        std_ret = group_returns.std()
        
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(annualization_factor)
        else:
            sharpe = 0.0
        
        results.append({
            'state': int(state),
            'mean_return': float(mean_ret),
            'std_return': float(std_ret),
            'sharpe': float(sharpe),
            'count': len(group_returns),
            'cumulative_return': float((1 + group_returns).prod() - 1)
        })
    
    return pd.DataFrame(results).set_index('state')


class GMMRegimeDetector:
    """
    Gaussian Mixture Model for regime detection (non-temporal fallback).
    
    Use when temporal structure is not important, or as simpler alternative to HMM.
    
    Examples:
        >>> detector = GMMRegimeDetector(n_components=3, random_state=42)
        >>> detector.fit(features)
        >>> states = detector.predict(features)
    """
    
    def __init__(
        self,
        n_components: int = 3,
        covariance_type: str = 'full',
        random_state: int = 42
    ):
        """Initialize GMM detector."""
        self.n_components = n_components
        self.covariance_type = covariance_type
        self.random_state = random_state
        
        self.model = GaussianMixture(
            n_components=n_components,
            covariance_type=covariance_type,
            random_state=random_state
        )
        
        self.is_fitted = False
        self.feature_names = None
    
    def fit(self, features: pd.DataFrame) -> 'GMMRegimeDetector':
        """Fit GMM to features."""
        if features.isnull().any().any():
            raise ValueError("Features contain NaN values.")
        
        self.feature_names = list(features.columns)
        X = features.values
        self.model.fit(X)
        self.is_fitted = True
        
        return self
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Predict cluster assignments."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        X = features.values
        labels = self.model.predict(X)
        
        return pd.Series(labels, index=features.index, name='regime')
    
    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Predict cluster probabilities."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        X = features.values
        probs = self.model.predict_proba(X)
        
        return pd.DataFrame(
            probs,
            index=features.index,
            columns=[f'prob_cluster_{i}' for i in range(self.n_components)]
        )
