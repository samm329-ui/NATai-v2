"""
Retry Utility
Provides an exponential backoff decorator for handling temporary network/API failures.
"""
import time
from functools import wraps

def retry_with_backoff(retries: int = 3, backoff_in_seconds: float = 1.0, max_backoff: float = 10.0):
    """
    A decorator that retries a function if it fails, with exponentially increasing wait times.
    
    Args:
        retries: Maximum number of retry attempts.
        backoff_in_seconds: Starting wait time in seconds.
        max_backoff: Maximum wait time in seconds to prevent stalling forever.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt >= retries:
                        print(f"[Retry] Function '{func.__name__}' failed after {retries} retries. Final error: {e}")
                        raise e
                    
                    # Calculate sleep time: 1s, 2s, 4s... capped at max_backoff
                    sleep_time = min(backoff_in_seconds * (2 ** attempt), max_backoff)
                    print(f"[Retry] '{func.__name__}' encountered an error: {e}. Retrying in {sleep_time} seconds (Attempt {attempt + 1}/{retries})...")
                    
                    time.sleep(sleep_time)
                    attempt += 1
        return wrapper
    return decorator

# Make it easy to import
__all__ = ["retry_with_backoff"]