import time
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def retry(func: Callable, retries: int = 3, delay: int = 2) -> Any:
    """
    Retry utility to handle transient API failures robustly.
    """
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            
    logger.error(f"Function {func.__name__} failed after {retries} retries.")
    return ""