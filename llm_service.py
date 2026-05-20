"""
LLM Service with Circuit Breaker and Fallback Cache
Student ID: BSCS24049
"""

import asyncio
import httpx
import hashlib
import json
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict

from circuit_breaker import CircuitBreaker, CircuitBreakerConfig


class LLMService:
    """Service for interacting with external LLM API with fault tolerance."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = 3.0  # CRITICAL: 3s timeout prevents thread starvation!
        
        # Circuit breaker configuration
        config = CircuitBreakerConfig(
            failure_threshold=3,      # Open after 3 failures
            timeout_seconds=30,       # Try again after 30 seconds
            success_threshold=2,      # Need 2 successes to close
            failure_window_seconds=30
        )
        self.circuit_breaker = CircuitBreaker(name="OpenAI_API", config=config)
        
        # LRU cache for fallback responses (size 100)
        self.cache: OrderedDict = OrderedDict()
        self.cache_max_size = 100
        
        # Mock response for when LLM is unavailable (degraded mode)
        self.mock_response = {
            "choices": [{"message": {"content": "[AI temporarily unavailable] Here's a generic suggestion: Review your document for clarity and structure."}}]
        }
    
    def _call_llm_sync(self, prompt: str) -> Dict:
        """Synchronous LLM call with timeout - this runs in FastAPI thread pool."""
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            return response.json()
    
    def _get_cached_or_mock_fallback(self, prompt: str) -> Dict:
        """Fallback function: return cached response or mock."""
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        
        # Check cache first
        if cache_key in self.cache:
            # Move to end (LRU)
            self.cache.move_to_end(cache_key)
            print(f"[LLMService] Cache HIT for key {cache_key[:8]}")
            return self.cache[cache_key]
        
        # Generate cache entry from mock
        mock_with_context = {
            **self.mock_response,
            "_cached": False,
            "_fallback_reason": "LLM circuit open or timeout"
        }
        
        # Store in cache if not full
        if len(self.cache) >= self.cache_max_size:
            self.cache.popitem(last=False)  # Remove LRU
        self.cache[cache_key] = mock_with_context
        
        print(f"[LLMService] Cache MISS - using MOCK fallback for {cache_key[:8]}")
        return mock_with_context
    
    def _store_in_cache(self, prompt: str, response: Dict):
        """Store successful response in cache for future fallbacks."""
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        if len(self.cache) >= self.cache_max_size:
            self.cache.popitem(last=False)
        self.cache[cache_key] = response
        print(f"[LLMService] Stored successful response in cache for {cache_key[:8]}")
    
    async def generate_suggestion(self, prompt: str) -> Dict:
        """
        Generate suggestion from LLM with circuit breaker protection.
        This is the main async endpoint called by FastAPI.
        """
        # Use circuit breaker to protect against cascade failures
        def sync_wrapper():
            return self._call_llm_sync(prompt)
        
        try:
            # Run sync call in thread pool (non-blocking for async FastAPI)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.circuit_breaker.call(sync_wrapper, self._get_cached_or_mock_fallback, prompt)
            )
            
            # Cache successful real responses
            if "_cached" not in result and "_fallback_reason" not in result:
                self._store_in_cache(prompt, result)
            
            return result
        except Exception as e:
            # Ultimate fallback - never let LLM failure bring down the app
            print(f"[LLMService] CRITICAL: All fallbacks failed: {e}")
            return self.mock_response
    
    def get_circuit_status(self) -> Dict:
        """Get current circuit breaker status for monitoring endpoint."""
        return self.circuit_breaker.get_metrics()