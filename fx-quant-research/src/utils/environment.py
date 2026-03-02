"""
Configuration management and environment utilities.

Provides:
- Configuration loading and validation via pydantic
- Environment capture for reproducibility
- Experiment logging with full audit trail
- Data file hashing for versioning
"""

import os
import hashlib
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import platform
import sys

from pydantic import BaseModel, Field, field_validator


# ==========================================
# Pydantic Configuration Models
# ==========================================

class DataConfig(BaseModel):
    """Data loading configuration."""
    raw_path: str
    processed_path: str = "data/processed/"
    timezone: str = "UTC"
    frequency: str = "D"


class ValidationConfig(BaseModel):
    """Data validation configuration."""
    spike_threshold: float = Field(gt=0, default=5.0)
    max_missing_pct: float = Field(ge=0, le=100, default=5.0)
    check_weekends: bool = True
    min_bars_required: int = Field(gt=0, default=100)


class CostConfig(BaseModel):
    """Transaction cost configuration."""
    spread_bps: Dict[str, float]
    slippage_coefficient: float = Field(gt=0, default=0.1)
    market_impact_exponent: float = Field(ge=0, le=1, default=0.5)
    market_impact_coefficient: float = Field(gt=0, default=0.05)
    enable_swap_costs: bool = False
    swap_rates_path: str = "data/swap_rates/"


class BacktestConfig(BaseModel):
    """Backtest engine configuration."""
    random_seed: int = 42
    execution_lag: int = Field(ge=1, default=1)
    initial_capital: float = Field(gt=0, default=100000.0)
    annualization_factor: int = Field(gt=0, default=252)


class RegimeConfig(BaseModel):
    """Regime detection configuration."""
    n_states: int = Field(ge=2, le=10, default=3)
    covariance_type: str = "full"
    max_iter: int = Field(gt=0, default=100)
    tol: float = Field(gt=0, default=1e-2)
    features: List[str] = ["returns", "volatility", "volume_zscore"]


class RiskConfig(BaseModel):
    """Risk management configuration."""
    max_drawdown_threshold: float = Field(le=0, default=-0.15)
    correlation_threshold: float = Field(ge=0, le=1, default=0.7)
    var_confidence: float = Field(ge=0, le=1, default=0.95)
    var_window: int = Field(gt=0, default=252)


class FeatureConfig(BaseModel):
    """Feature engineering configuration."""
    momentum_windows: List[int] = [5, 10, 20, 50]
    volatility_windows: List[int] = [10, 20, 60]
    rsi_period: int = Field(gt=0, default=14)
    zscore_window: int = Field(gt=0, default=20)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    experiment_log_path: str = "logs/experiment_log.json"
    state_transition_log: str = "logs/state_transitions.log"
    level: str = "INFO"


class Config(BaseModel):
    """Master configuration model."""
    data: DataConfig
    validation: ValidationConfig
    costs: CostConfig
    backtest: BacktestConfig
    regime: RegimeConfig
    risk: RiskConfig
    features: FeatureConfig
    logging: LoggingConfig


# ==========================================
# Configuration Loading
# ==========================================

def load_config(path: str = "config/config.yaml") -> Config:
    """
    Load and validate configuration from YAML file.
    
    Args:
        path: Path to configuration YAML file
        
    Returns:
        Validated Config object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config validation fails
        
    Examples:
        >>> config = load_config("config/config.yaml")
        >>> print(config.backtest.random_seed)
        42
    """
    config_path = Path(path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Validate and parse with pydantic
    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")
    
    return config


# ==========================================
# Environment Capture
# ==========================================

def capture_environment() -> Dict[str, Any]:
    """
    Capture full environment details for reproducibility.
    
    Returns:
        Dictionary with Python version, library versions, platform info
        
    Examples:
        >>> env = capture_environment()
        >>> print(env['python_version'])
        '3.10.5'
    """
    import pandas as pd
    import numpy as np
    import scipy
    
    env = {
        'timestamp': datetime.utcnow().isoformat(),
        'python_version': sys.version,
        'platform': platform.platform(),
        'libraries': {
            'pandas': pd.__version__,
            'numpy': np.__version__,
            'scipy': scipy.__version__,
        }
    }
    
    # Try to get optional libraries
    try:
        import statsmodels
        env['libraries']['statsmodels'] = statsmodels.__version__
    except ImportError:
        pass
    
    try:
        import hmmlearn
        env['libraries']['hmmlearn'] = hmmlearn.__version__
    except ImportError:
        pass
    
    try:
        import sklearn
        env['libraries']['sklearn'] = sklearn.__version__
    except ImportError:
        pass
    
    return env


# ==========================================
# Data Hashing
# ==========================================

def hash_file(filepath: str) -> str:
    """
    Calculate SHA256 hash of file for versioning.
    
    Args:
        filepath: Path to file
        
    Returns:
        SHA256 hash as hex string
        
    Examples:
        >>> hash_val = hash_file("data/raw/eurusd.csv")
        >>> len(hash_val)
        64
    """
    sha256_hash = hashlib.sha256()
    
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


# ==========================================
# Experiment Logging
# ==========================================

def log_experiment(
    config: Dict[str, Any],
    environment: Dict[str, Any],
    results: Dict[str, Any],
    data_files: Optional[Dict[str, str]] = None,
    log_path: str = "logs/experiment_log.json"
) -> str:
    """
    Log experiment with full reproducibility information.
    
    Args:
        config: Configuration dictionary
        environment: Environment info from capture_environment()
        results: Backtest results/metrics
        data_files: Dict mapping identifiers to file paths
        log_path: Path to experiment log file
        
    Returns:
        Experiment UUID
        
    Examples:
        >>> exp_id = log_experiment(config_dict, env, metrics)
        >>> print(f"Logged experiment: {exp_id}")
    """
    import uuid
    
    # Generate UUID
    exp_id = str(uuid.uuid4())
    
    # Hash data files
    data_hashes = {}
    if data_files:
        for key, filepath in data_files.items():
            if os.path.exists(filepath):
                data_hashes[key] = hash_file(filepath)
    
    # Create log entry
    log_entry = {
        'experiment_id': exp_id,
        'timestamp': datetime.utcnow().isoformat(),
        'config': config,
        'environment': environment,
        'data_hashes': data_hashes,
        'results': results
    }
    
    # Ensure log directory exists
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Append to log file
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_path, 'w') as f:
        json.dump(logs, f, indent=2)
    
    return exp_id


def load_experiment(
    exp_id: str,
    log_path: str = "logs/experiment_log.json"
) -> Optional[Dict[str, Any]]:
    """
    Load experiment by UUID.
    
    Args:
        exp_id: Experiment UUID
        log_path: Path to experiment log file
        
    Returns:
        Experiment log entry or None if not found
        
    Examples:
        >>> exp = load_experiment("abc-123-def")
        >>> if exp:
        ...     print(exp['results'])
    """
    if not os.path.exists(log_path):
        return None
    
    with open(log_path, 'r') as f:
        logs = json.load(f)
    
    for entry in logs:
        if entry.get('experiment_id') == exp_id:
            return entry
    
    return None


def verify_reproducibility(
    exp_id_1: str,
    exp_id_2: str,
    tolerance: float = 1e-10,
    log_path: str = "logs/experiment_log.json"
) -> bool:
    """
    Verify two experiments are identical within tolerance.
    
    Args:
        exp_id_1: First experiment UUID
        exp_id_2: Second experiment UUID
        tolerance: Numerical tolerance for comparison
        log_path: Path to experiment log file
        
    Returns:
        True if experiments match
        
    Examples:
        >>> match = verify_reproducibility(exp1, exp2)
        >>> print(f"Reproducible: {match}")
    """
    exp1 = load_experiment(exp_id_1, log_path)
    exp2 = load_experiment(exp_id_2, log_path)
    
    if exp1 is None or exp2 is None:
        return False
    
    # Compare key fields
    if exp1.get('config') != exp2.get('config'):
        return False
    
    if exp1.get('data_hashes') != exp2.get('data_hashes'):
        return False
    
    # Compare numerical results within tolerance
    results1 = exp1.get('results', {})
    results2 = exp2.get('results', {})
    
    for key in results1.keys():
        if key not in results2:
            return False
        
        val1 = results1[key]
        val2 = results2[key]
        
        # Compare numerically if both are numbers
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if abs(val1 - val2) > tolerance:
                return False
        else:
            if val1 != val2:
                return False
    
    return True
