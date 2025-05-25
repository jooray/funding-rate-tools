import time
from .database import get_funding_interval_hours, get_last_funding_time

def should_refresh_symbol(symbol: str, exchange_value: str) -> bool:
    """
    Determines if a symbol should be refreshed based on smart refresh logic.
    Returns True if refresh is needed, False otherwise.
    """
    last_time_ms = get_last_funding_time(symbol, exchange_value)
    if last_time_ms is None:
        # No data exists, should refresh
        return True

    interval_hours = get_funding_interval_hours(symbol, exchange_value)
    if interval_hours is None:
        # No interval info, should refresh to be safe
        return True

    current_time_ms = int(time.time() * 1000)
    interval_ms = interval_hours * 60 * 60 * 1000

    # Check if enough time has passed for a potential new funding rate
    return current_time_ms >= (last_time_ms + interval_ms)
