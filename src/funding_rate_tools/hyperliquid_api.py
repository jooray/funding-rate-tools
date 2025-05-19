import requests
import time

HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def fetch_funding_rate_history_hyperliquid(symbol: str, start_time_ms: int | None = None) -> list[dict]:
    """
    Fetches historical funding rates for a symbol from Hyperliquid.
    Returns list of {'fundingTime': ..., 'fundingRate': ...}.
    """
    all_rates = []
    current_start = start_time_ms or 0

    while True:
        payload = {"type": "fundingHistory", "coin": symbol.upper()}
        if current_start:
            payload["startTime"] = current_start

        try:
            resp = requests.post(
                HYPERLIQUID_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()  # list of dicts
        except requests.RequestException:
            return all_rates

        if not data:
            break

        for item in data:
            all_rates.append({
                "fundingTime": int(item["time"]),
                "fundingRate": float(item["fundingRate"])
            })

        current_start = data[-1]["time"] + 1
        time.sleep(0.2)

    return all_rates
