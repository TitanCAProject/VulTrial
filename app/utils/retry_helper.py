"""Retry helper for API calls with exponential backoff"""

import time
import random
from typing import Callable, Any, Type, Tuple
from functools import wraps


class RetryError(Exception):
    """Raised when all retry attempts fail"""
    pass


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retrying function calls with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (2.0 = double each time)
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exception types to catch and retry
    
    Returns:
        Decorated function that retries on failure
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    # Check if it's a rate limit error (specific handling)
                    error_msg = str(e).lower()
                    if 'rate limit' in error_msg or '429' in error_msg:
                        # Rate limit - use longer delay
                        delay = min(delay * 2, max_delay)
                        print(f"  ⚠️  Rate limit hit. Waiting {delay:.1f}s before retry {attempt + 1}/{max_attempts}...")
                    else:
                        print(f"  ⚠️  API error: {str(e)[:100]}. Retrying in {delay:.1f}s ({attempt + 1}/{max_attempts})...")
                    
                    time.sleep(delay)
            
            # All attempts failed
            raise RetryError(f"Failed after {max_attempts} attempts. Last error: {last_exception}")
        
        return wrapper
    return decorator


def api_call_with_retry(func: Callable, *args, **kwargs) -> Any:
    """
    Helper function to call an API with retry logic
    
    Args:
        func: Function to call
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function
    
    Returns:
        Function result
    
    Raises:
        RetryError: If all retry attempts fail
    """
    @retry_with_backoff(max_attempts=3, initial_delay=1.0, max_delay=60.0)
    def _wrapped():
        return func(*args, **kwargs)
    
    return _wrapped()


