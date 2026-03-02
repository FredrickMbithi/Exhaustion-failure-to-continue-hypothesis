"""
Seed management for reproducible backtesting.

Provides utilities to set global random seeds for numpy, random module,
and return random state objects for sklearn/hmmlearn components.
"""

import random
from typing import Optional

import numpy as np


class SeedManager:
    """
    Manage random seeds for reproducible experiments.
    
    Examples:
        >>> seed_mgr = SeedManager(seed=42)
        >>> seed_mgr.set_global_seed()
        >>> rng = seed_mgr.get_random_state()
        >>> random_values = rng.normal(0, 1, 100)
    """
    
    def __init__(self, seed: int = 42):
        """
        Initialize seed manager.
        
        Args:
            seed: Random seed value
        """
        self.seed = seed
    
    def set_global_seed(self) -> None:
        """
        Set global random seeds for reproducibility.
        
        Sets seeds for:
        - Python's random module
        - NumPy's random module
        
        Examples:
            >>> seed_mgr = SeedManager(42)
            >>> seed_mgr.set_global_seed()
        """
        random.seed(self.seed)
        np.random.seed(self.seed)
    
    def get_random_state(self, seed: Optional[int] = None) -> np.random.RandomState:
        """
        Get NumPy RandomState object for explicit passing.
        
        Use this for sklearn estimators, hmmlearn models, etc.
        
        Args:
            seed: Optional seed override (uses instance seed if None)
            
        Returns:
            NumPy RandomState object
            
        Examples:
            >>> seed_mgr = SeedManager(42)
            >>> rng = seed_mgr.get_random_state()
            >>> # Pass to sklearn
            >>> from sklearn.model_selection import train_test_split
            >>> X_train, X_test = train_test_split(X, random_state=rng)
        """
        seed_to_use = seed if seed is not None else self.seed
        return np.random.RandomState(seed_to_use)
    
    def get_seed(self) -> int:
        """
        Get current seed value.
        
        Returns:
            Current seed value
        """
        return self.seed


def set_global_seed(seed: int = 42) -> None:
    """
    Convenience function to set global seeds.
    
    Args:
        seed: Random seed value
        
    Examples:
        >>> set_global_seed(42)
        >>> # All subsequent random operations use this seed
    """
    random.seed(seed)
    np.random.seed(seed)
