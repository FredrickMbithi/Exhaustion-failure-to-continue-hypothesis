"""
Strategy lifecycle finite state machine.

Manages strategy states and transitions with condition checking
and comprehensive logging.
"""

import json
import logging
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Callable, Optional, Any

import pandas as pd


class StrategyState(Enum):
    """Strategy lifecycle states."""
    RESEARCH = auto()
    PAPER = auto()
    LIVE_PILOT = auto()
    LIVE_FULL = auto()
    DEGRADED = auto()
    DISABLED = auto()


class StrategyFSM:
    """
    Finite State Machine for strategy lifecycle management.
    
    States:
    - RESEARCH: Strategy under development
    - PAPER: Paper trading/simulation
    - LIVE_PILOT: Small live position
    - LIVE_FULL: Full production
    - DEGRADED: Performance issues detected
    - DISABLED: Strategy stopped
    
    Examples:
        >>> fsm = StrategyFSM(initial_state=StrategyState.RESEARCH)
        >>> can_promote = fsm.can_transition('promote_to_paper')
        >>> if can_promote:
        ...     fsm.transition('promote_to_paper', sharpe=1.5)
    """
    
    def __init__(
        self,
        initial_state: StrategyState = StrategyState.RESEARCH,
        log_file: str = 'logs/state_transitions.log'
    ):
        """
        Initialize strategy FSM.
        
        Args:
            initial_state: Starting state
            log_file: Path to transition log file
        """
        self.current_state = initial_state
        self.log_file = log_file
        
        # Define valid transitions
        self.transitions = {
            (StrategyState.RESEARCH, 'promote_to_paper'): StrategyState.PAPER,
            (StrategyState.PAPER, 'promote_to_pilot'): StrategyState.LIVE_PILOT,
            (StrategyState.PAPER, 'demote_to_research'): StrategyState.RESEARCH,
            (StrategyState.LIVE_PILOT, 'promote_to_full'): StrategyState.LIVE_FULL,
            (StrategyState.LIVE_PILOT, 'degrade'): StrategyState.DEGRADED,
            (StrategyState.LIVE_PILOT, 'disable'): StrategyState.DISABLED,
            (StrategyState.LIVE_FULL, 'degrade'): StrategyState.DEGRADED,
            (StrategyState.LIVE_FULL, 'disable'): StrategyState.DISABLED,
            (StrategyState.DEGRADED, 'recover'): StrategyState.LIVE_PILOT,
            (StrategyState.DEGRADED, 'disable'): StrategyState.DISABLED,
            (StrategyState.DISABLED, 'restart'): StrategyState.RESEARCH,
        }
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Setup structured logging for state transitions."""
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logger
        self.logger = logging.getLogger('StrategyFSM')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        
        # Add handler
        if not self.logger.handlers:
            self.logger.addHandler(fh)
    
    def can_transition(self, event: str) -> bool:
        """
        Check if transition is valid from current state.
        
        Args:
            event: Transition event name
            
        Returns:
            True if transition is allowed
            
        Examples:
            >>> if fsm.can_transition('promote_to_paper'):
            ...     print("Can promote to paper trading")
        """
        return (self.current_state, event) in self.transitions
    
    def transition(
        self,
        event: str,
        conditions_met: bool = True,
        **metadata
    ) -> bool:
        """
        Attempt state transition.
        
        Args:
            event: Transition event name
            conditions_met: Whether transition conditions satisfied
            **metadata: Additional context (sharpe, drawdown, etc.)
            
        Returns:
            True if transition successful
            
        Raises:
            ValueError: If transition not allowed
            
        Examples:
            >>> success = fsm.transition(
            ...     'promote_to_paper',
            ...     conditions_met=True,
            ...     sharpe=1.5,
            ...     max_dd=-0.08
            ... )
        """
        if not self.can_transition(event):
            raise ValueError(
                f"Invalid transition '{event}' from state {self.current_state.name}"
            )
        
        if not conditions_met:
            self.logger.warning(
                f"Transition '{event}' attempted but conditions not met. "
                f"Remaining in {self.current_state.name}"
            )
            return False
        
        # Get new state
        new_state = self.transitions[(self.current_state, event)]
        old_state = self.current_state
        
        # Log transition
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'previous_state': old_state.name,
            'new_state': new_state.name,
            'event': event,
            'conditions_met': conditions_met,
            'metadata': metadata
        }
        
        self.logger.info(json.dumps(log_entry))
        
        # Update state
        self.current_state = new_state
        
        # Execute state callbacks
        self._on_exit_state(old_state, metadata)
        self._on_enter_state(new_state, metadata)
        
        return True
    
    def _on_enter_state(self, state: StrategyState, context: Dict) -> None:
        """
        Callback when entering a state.
        
        Override this method for state-specific initialization.
        """
        pass
    
    def _on_exit_state(self, state: StrategyState, context: Dict) -> None:
        """
        Callback when exiting a state.
        
        Override this method for state-specific cleanup.
        """
        pass
    
    def get_state(self) -> StrategyState:
        """Get current state."""
        return self.current_state


def check_sharpe_threshold(metrics: Dict[str, float], threshold: float = 1.0) -> bool:
    """
    Check if Sharpe ratio meets threshold.
    
    Args:
        metrics: Dictionary with 'sharpe' key
        threshold: Minimum Sharpe ratio
        
    Returns:
        True if threshold met
        
    Examples:
        >>> metrics = {'sharpe': 1.5, 'max_drawdown': -0.12}
        >>> if check_sharpe_threshold(metrics, threshold=1.0):
        ...     print("Sharpe threshold met")
    """
    return metrics.get('sharpe', 0.0) >= threshold


def check_drawdown_breach(metrics: Dict[str, float], max_dd: float = -0.15) -> bool:
    """
    Check if drawdown breached threshold.
    
    Args:
        metrics: Dictionary with 'max_drawdown' key
        max_dd: Maximum allowed drawdown (negative value)
        
    Returns:
        True if drawdown breached (worse than threshold)
        
    Examples:
        >>> if check_drawdown_breach(metrics, max_dd=-0.15):
        ...     print("Drawdown threshold breached - degrading strategy")
    """
    current_dd = metrics.get('max_drawdown', 0.0)
    return current_dd < max_dd  # More negative = worse


def check_drift_detection(
    recent_metrics: Dict[str, float],
    baseline_metrics: Dict[str, float],
    alpha: float = 0.05
) -> bool:
    """
    Detect performance drift using statistical test.
    
    Uses simple comparison of Sharpe ratios. In production, would use
    returns series with proper statistical test (t-test, KS test).
    
    Args:
        recent_metrics: Recent performance metrics
        baseline_metrics: Baseline performance metrics
        alpha: Significance level
        
    Returns:
        True if significant drift detected
        
    Examples:
        >>> recent = {'sharpe': 0.5, 'win_rate': 0.45}
        >>> baseline = {'sharpe': 1.5, 'win_rate': 0.55}
        >>> if check_drift_detection(recent, baseline):
        ...     print("Performance drift detected")
    """
    recent_sharpe = recent_metrics.get('sharpe', 0.0)
    baseline_sharpe = baseline_metrics.get('sharpe', 0.0)
    
    # Simple check: if recent Sharpe drops below 50% of baseline
    # In production: use proper statistical test on returns series
    drift_threshold = 0.5
    
    if baseline_sharpe > 0:
        ratio = recent_sharpe / baseline_sharpe
        return ratio < drift_threshold
    
    return False
