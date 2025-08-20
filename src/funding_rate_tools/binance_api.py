import requests
import time
from .config import BINANCE_API_BASE_URL, FUNDING_RATE_HISTORY_ENDPOINT, TICKER_PRICE_ENDPOINT, FUNDING_INFO_ENDPOINT

MAX_RESULTS_PER_REQUEST = 1000

def fetch_funding_rate_history(symbol: str, start_time_ms: int | None = None) -> list[dict]:
    """
    Fetches historical funding rates for a symbol from Binance.
    If start_time_ms is provided, fetches rates after that time.
    Handles pagination to retrieve all available new rates.
    """
    all_rates = []
    url = f"{BINANCE_API_BASE_URL}{FUNDING_RATE_HISTORY_ENDPOINT}"

    current_start_time = start_time_ms + 1 if start_time_ms else None

    while True:
        params = {
            "symbol": symbol.upper(),
            "limit": MAX_RESULTS_PER_REQUEST
        }
        if current_start_time:
            params["startTime"] = current_start_time

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching funding rates for {symbol}: {e}")
            return all_rates

        if not data:
            break

        all_rates.extend(data)

        if len(data) < MAX_RESULTS_PER_REQUEST:
            break

        current_start_time = int(data[-1]['fundingTime']) + 1
        time.sleep(0.2)

    return all_rates

def fetch_current_price(symbol: str) -> float | None:
    """Fetches the current market price for a given symbol."""
    url = f"{BINANCE_API_BASE_URL}{TICKER_PRICE_ENDPOINT}"
    params = {"symbol": symbol.upper()}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data['price'])
    except requests.RequestException as e:
        print(f"Error fetching current price for {symbol}: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error parsing price data for {symbol}: {e}")
        return None

def fetch_funding_info(symbol: str) -> int | None:
    """Fetches funding-interval hours for a symbol."""
    url = f"{BINANCE_API_BASE_URL}{FUNDING_INFO_ENDPOINT}"
    params = {"symbol": symbol.upper()}
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        sym_u = symbol.upper()
        # Binance returns a list; for invalid symbols, it may return many items.
        # Find the exact symbol match; if not found, return None.
        if isinstance(data, list) and data:
            for item in data:
                try:
                    if item.get("symbol") == sym_u:
                        return int(item.get("fundingIntervalHours", 0)) or None
                except Exception:
                    continue
            return None
        # Some edge cases might return a single dict
        if isinstance(data, dict) and data.get("symbol") == sym_u:
            try:
                val = int(data.get("fundingIntervalHours", 0))
                return val or None
            except Exception:
                return None
    except requests.RequestException:
        pass
    return None
