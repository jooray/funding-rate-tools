import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "funding_rates.db")

BINANCE_API_BASE_URL = "https://fapi.binance.com"
FUNDING_RATE_HISTORY_ENDPOINT = "/fapi/v1/fundingRate"
TICKER_PRICE_ENDPOINT = "/fapi/v1/ticker/price"
FUNDING_INFO_ENDPOINT = "/fapi/v1/fundingInfo"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Default symbols if none are provided by the user
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
