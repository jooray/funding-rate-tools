import requests
import time

HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def _hl_coin_from_symbol(symbol: str) -> str:
    """
    Hyperliquid expects base coin tickers (e.g., BTC, ETH), not Binance-style pairs like BTCUSDT.
    Map common symbols by stripping stable-coin suffixes if present.
    """
    s = symbol.upper()
    for suffix in ("USDT", "USD", "USDC"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s

def fetch_funding_rate_history(symbol: str, start_time_ms: int | None = None) -> list[dict]:
    """
    Fetches historical funding rates for a symbol from Hyperliquid.
    Returns list of {'fundingTime': ..., 'fundingRate': ...}.
    """
    all_rates = []
    current_start = start_time_ms or 0
    coin = _hl_coin_from_symbol(symbol)

    while True:
        # Hyperliquid requires startTime in payload; include it even when 0
        payload = {"type": "fundingHistory", "coin": coin, "startTime": current_start}

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

def fetch_funding_info(symbol: str) -> int | None:
    """
    Infers Hyperliquid funding interval (in hours) by sampling recent funding history.
    Returns None if it cannot be determined.
    """
    coin = _hl_coin_from_symbol(symbol)
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 48 * 3600 * 1000  # last ~2 days
    try:
        resp = requests.post(
            HYPERLIQUID_URL,
            json={"type": "fundingHistory", "coin": coin, "startTime": start_ms},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json() or []
    except requests.RequestException:
        return None

    if len(data) < 2:
        return None

    times = [int(x.get("time", 0)) for x in data if x.get("time")]
    times.sort()
    if len(times) < 2:
        return None

    deltas = [t2 - t1 for t1, t2 in zip(times, times[1:]) if t2 > t1]
    if not deltas:
        return None

    # Find the most common delta (mode) to reduce noise
    from collections import Counter
    delta_ms, _ = Counter(deltas).most_common(1)[0]
    hours = round(delta_ms / (3600 * 1000))
    return hours if hours > 0 else None
