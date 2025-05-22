import requests
import time

BYBIT_URL = "https://api.bybit.com"

def fetch_funding_rate_history_bybit(symbol: str, start_time_ms: int | None = None) -> list[dict]:
    """
    Fetches historical funding rates for a symbol from Bybit.
    Returns list of {'fundingTime': ..., 'fundingRate': ...}.
    """
    all_rates = []

    # For forward-fill (getting newer data), we use startTime
    # For backfill (getting older data), we use endTime
    if start_time_ms:
        # Forward-fill mode: get data from start_time_ms onwards
        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "limit": 200,
            "startTime": start_time_ms
        }

        try:
            resp = requests.get(
                f"{BYBIT_URL}/v5/market/funding/history",
                params=params,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return all_rates

        if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
            return all_rates

        rates_batch = data["result"]["list"]

        # Filter to only include rates newer than start_time_ms
        for item in rates_batch:
            timestamp = int(item["fundingRateTimestamp"])
            if timestamp > start_time_ms:
                all_rates.append({
                    "fundingTime": timestamp,
                    "fundingRate": float(item["fundingRate"])
                })
    else:
        # Backfill mode: get recent data and paginate backwards
        end_time_ms = None

        while True:
            params = {
                "category": "linear",
                "symbol": symbol.upper(),
                "limit": 200
            }
            if end_time_ms:
                params["endTime"] = end_time_ms

            try:
                resp = requests.get(
                    f"{BYBIT_URL}/v5/market/funding/history",
                    params=params,
                    timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                return all_rates

            if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
                break

            rates_batch = data["result"]["list"]

            for item in rates_batch:
                all_rates.append({
                    "fundingTime": int(item["fundingRateTimestamp"]),
                    "fundingRate": float(item["fundingRate"])
                })

            if len(rates_batch) < 200:
                break

            # Get older data by setting endTime to the oldest timestamp we just fetched
            end_time_ms = int(rates_batch[-1]["fundingRateTimestamp"]) - 1
            time.sleep(0.2)

    return all_rates

def fetch_funding_info_bybit(symbol: str) -> int | None:
    """Fetches funding interval hours for a Bybit symbol."""
    params = {
        "category": "linear",
        "symbol": symbol.upper()
    }
    try:
        resp = requests.get(
            f"{BYBIT_URL}/v5/market/instruments-info",
            params=params,
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()

        if (data.get("retCode") == 0 and
            data.get("result", {}).get("list")):
            interval_minutes = data["result"]["list"][0].get("fundingInterval")
            if interval_minutes:
                return int(interval_minutes) // 60  # Convert minutes to hours
    except requests.RequestException:
        pass
    return None
