"""
Trading strategies for FX quantitative research.

Available strategies:
- ExhaustionFailureStrategy: Mean reversion based on exhaustion-failure patterns
"""

from .exhaustion_failure import ExhaustionFailureStrategy, validate_strategy_setup

__all__ = [
    'ExhaustionFailureStrategy',
    'validate_strategy_setup',
]
