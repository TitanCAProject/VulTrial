"""Simple retry helper with exponential backoff"""

import time
import functools
from typing import Callable, TypeVar, Any

T = TypeVar('T')


class RetryError(Exception):
    """Raised when all retry attempts fail"""
    pass


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay after each attempt
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        # Wait before retrying
                        time.sleep(min(delay, max_delay))
                        delay *= backoff_factor
            
            # All attempts failed
            raise RetryError(f"Failed after {max_attempts} attempts") from last_exception
        
        return wrapper
    return decorator

