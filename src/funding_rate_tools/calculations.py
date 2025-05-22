import time
from datetime import datetime, timedelta, timezone
from .database import get_funding_rates
from .database import get_funding_interval_hours

DAYS_IN_YEAR = 365

def calculate_pa_rate(symbol: str, rates_data: list[dict], source: str = None) -> float | None:
    """
    Calculates the per annum (p.a.) funding rate from a list of funding rate data.
    The rate is from the perspective of a short position (positive if shorts are paid).
    """
    if not rates_data:
        return None

    interval = get_funding_interval_hours(symbol, source)
    if not interval:
        return None

    total = sum(item['funding_rate'] for item in rates_data)
    avg_per_interval = total / len(rates_data)

    intervals_per_day = 24 / interval
    pa = avg_per_interval * intervals_per_day * DAYS_IN_YEAR
    return pa * 100

def get_rates_for_period(symbol: str, period_days: int | None = None, since_date_str: str | None = None, source: str = None) -> list[dict]:
    """
    Retrieves funding rates for a specified period (number of days or since a date).
    """
    now_ms = int(time.time() * 1000)
    start_time_ms = 0

    if since_date_str:
        try:
            dt_object = datetime.strptime(since_date_str, "%Y-%m-%d")
            dt_object = dt_object.replace(tzinfo=timezone.utc)
            start_time_ms = int(dt_object.timestamp() * 1000)
        except ValueError:
            print(f"Error: Invalid date format for --since. Use YYYY-MM-DD.")
            return []
    elif period_days is not None:
        start_time_ms = now_ms - (period_days * 24 * 60 * 60 * 1000)
    else:
        start_time_ms = now_ms - (14 * 24 * 60 * 60 * 1000)

    return get_funding_rates(symbol, start_time_ms, now_ms, source)

def get_start_time_for_cli_period(args) -> int | None:
    """Determines the start timestamp in milliseconds based on CLI arguments."""
    now = datetime.now(timezone.utc)
    start_datetime = None

    if args.last_day:
        start_datetime = now - timedelta(days=1)
    elif args.last_week:
        start_datetime = now - timedelta(weeks=1)
    elif args.last_month:
        start_datetime = now - timedelta(days=30)
    elif args.since:
        try:
            start_datetime = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Error: Invalid date format for --since. Use YYYY-MM-DD.")
            return None

    if start_datetime:
        return int(start_datetime.timestamp() * 1000)
    return 0
