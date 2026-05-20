"""
Circuit Breaker Pattern Implementation for LLM API Fault Tolerance
Student ID: BSCS24121
"""

import time
import threading
from enum import Enum
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass
from collections import deque


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation, calls go through
    OPEN = "open"          # Failing fast, no calls to LLM
    HALF_OPEN = "half_open"  # Testing if LLM recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures needed to open circuit
    timeout_seconds: int = 60       # Time in OPEN state before half-open
    success_threshold: int = 2      # Successes needed in half-open to close
    failure_window_seconds: int = 60  # Window for counting failures


class CircuitBreaker:
    """
    Thread-safe circuit breaker for external API calls.
    Prevents cascade failures by failing fast when dependency is unhealthy.
    """
    
    def __init__(self, name: str = "LLM_API", config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()
        self._failure_timestamps: deque = deque()
        self._lock = threading.RLock()
        
    @property
    def state(self) -> CircuitState:
        with self._lock:
            # Auto-transition from OPEN to HALF_OPEN after timeout
            if self._state == CircuitState.OPEN:
                if datetime.now() - self._last_state_change > timedelta(seconds=self.config.timeout_seconds):
                    self._transition_to_half_open()
            return self._state
    
    def _transition_to_half_open(self):
        with self._lock:
            print(f"[CircuitBreaker:{self.name}] Transitioning OPEN → HALF_OPEN at {datetime.now()}")
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            self._last_state_change = datetime.now()
    
    def _transition_to_open(self):
        with self._lock:
            print(f"[CircuitBreaker:{self.name}] Transitioning {self._state.value} → OPEN at {datetime.now()}")
            self._state = CircuitState.OPEN
            self._last_state_change = datetime.now()
    
    def _transition_to_closed(self):
        with self._lock:
            print(f"[CircuitBreaker:{self.name}] Transitioning {self._state.value} → CLOSED at {datetime.now()}")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._failure_timestamps.clear()
    
    def _record_failure(self):
        with self._lock:
            now = datetime.now()
            self._failure_timestamps.append(now)
            self._last_failure_time = now
            
            # Remove failures outside window
            cutoff = now - timedelta(seconds=self.config.failure_window_seconds)
            while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
                self._failure_timestamps.popleft()
            
            self._failure_count = len(self._failure_timestamps)
            
            if self._state == CircuitState.CLOSED and self._failure_count >= self.config.failure_threshold:
                self._transition_to_open()
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()
    
    def _record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
                self._failure_timestamps.clear()
    
    def call(self, func: Callable, fallback: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker with fallback.
        
        Args:
            func: Primary function to call (e.g., LLM API)
            fallback: Fallback function when circuit is OPEN
            *args, **kwargs: Arguments for primary function
            
        Returns:
            Result from either primary or fallback function
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            print(f"[CircuitBreaker:{self.name}] Circuit OPEN - using fallback")
            return fallback(*args, **kwargs)
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            print(f"[CircuitBreaker:{self.name}] Call failed: {e}")
            self._record_failure()
            
            # If we're now in HALF_OPEN or still CLOSED but with failures,
            # execute fallback for this call as well
            if self.state != CircuitState.CLOSED:
                return fallback(*args, **kwargs)
            raise e
    
    def get_metrics(self) -> Dict:
        """Get current circuit breaker metrics for monitoring."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count_60s": self._failure_count,
                "success_count_half_open": self._success_count,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "time_in_current_state": (datetime.now() - self._last_state_change).total_seconds()
            }