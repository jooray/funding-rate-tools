import argparse
import time
from datetime import datetime, timezone
import os

from . import config, database, binance_api, calculations, hyperliquid_api, bybit_api
from .html_template import get_html_content
from .database import get_funding_interval_hours, store_funding_info, store_funding_rates
from .config import Exchange

def main():
    """Main function for the dashboard generator."""
    parser = argparse.ArgumentParser(description="Generate funding rate dashboard.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=config.DEFAULT_SYMBOLS,
        help=f"Space-separated list of symbols (e.g., BTCUSDT ETHUSDT). Default: {' '.join(config.DEFAULT_SYMBOLS)}",
        metavar="SYMBOL"
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Do not refresh data from Binance API; use existing data in database."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(config.PROJECT_ROOT, "dashboard.html"),
        help="Output HTML file path. Default: dashboard.html in project root."
    )
    parser.add_argument(
        "--exchange",
        choices=["binance", "hyperliquid", "bybit"],
        default="binance",
        help="Exchange to fetch funding rates from. Default: binance"
    )

    args = parser.parse_args()
    exchange = Exchange(args.exchange)
    symbols = [s.upper() for s in args.symbols]

    if not args.no_refresh:
        print("Refreshing data for dashboard...")
        for symbol in symbols:
            if get_funding_interval_hours(symbol, exchange.value) is None:
                source = exchange.value
                if exchange == Exchange.HYPERLIQUID:
                    store_funding_info(symbol, 8, source)
                elif exchange == Exchange.BYBIT:
                    hrs = bybit_api.fetch_funding_info(symbol)
                    if hrs:
                        store_funding_info(symbol, hrs, source)
                else:  # BINANCE
                    hrs = binance_api.fetch_funding_info(symbol)
                    if hrs:
                        store_funding_info(symbol, hrs, source)

            print(f"Fetching data for {symbol}...")
            last_time_ms = database.get_last_funding_time(symbol, exchange.value)
            fetch_start_time = last_time_ms + 1 if last_time_ms else None

            try:
                source = exchange.value
                if exchange == Exchange.HYPERLIQUID:
                    new_rates = hyperliquid_api.fetch_funding_rate_history(symbol, start_time_ms=fetch_start_time)
                elif exchange == Exchange.BYBIT:
                    new_rates = bybit_api.fetch_funding_rate_history(symbol, start_time_ms=fetch_start_time)
                else:  # BINANCE
                    new_rates = binance_api.fetch_funding_rate_history(symbol, start_time_ms=fetch_start_time)
                if new_rates:
                    store_funding_rates(symbol, new_rates, source)
                    print(f"Stored {len(new_rates)} new rate(s) for {symbol}.")
                else:
                    print(f"No new rates found for {symbol} or API returned no data.")
            except Exception as e:
                print(f"Warning: Error refreshing data for {symbol}: {e}. Dashboard will use existing data.")
            time.sleep(0.5)

    dashboard_pairs_data = []
    now_ms = int(time.time() * 1000)

    for symbol in symbols:
        interval = get_funding_interval_hours(symbol, exchange.value) or (8 if exchange != Exchange.BINANCE else None)
        current_price_str = "N/A" if exchange != Exchange.BINANCE else (
            f"{(val:=binance_api.fetch_current_price(symbol)):.2f}" if (val:=binance_api.fetch_current_price(symbol)) is not None else "N/A"
        )

        # Data for 7-day P.A. rate summary
        rates_7d = calculations.get_rates_for_period(symbol, period_days=7, source=exchange.value)
        pa_rate_7d = calculations.calculate_pa_rate(symbol, rates_7d)

        # Data for 14-day P.A. rate summary
        rates_14d = calculations.get_rates_for_period(symbol, period_days=14, source=exchange.value)
        pa_rate_14d = calculations.calculate_pa_rate(symbol, rates_14d)

        # Fetch ALL historical rates for the chart
        all_rates_db = database.get_funding_rates(symbol, start_time_ms=0, end_time_ms=now_ms, source=exchange.value)

        # Prepare all rates for JavaScript (timestamps and rates)
        # Ensure rates are sorted by time, which get_funding_rates should already do.
        all_rates_for_js = [
            {"time": r['funding_time'], "rate": r['funding_rate']}
            for r in all_rates_db
        ]

        dashboard_pairs_data.append({
            "symbol": symbol,
            "current_price": current_price_str,
            "pa_rate_7d": pa_rate_7d, # For summary text
            "pa_rate_14d": pa_rate_14d, # For summary text
            "interval_hours": interval,
            "all_rates_data": all_rates_for_js # All data for dynamic JS charts
        })
        time.sleep(0.2) # Small delay if fetching prices for multiple symbols

    html_content = get_html_content(dashboard_pairs_data)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Dashboard generated successfully: {os.path.abspath(args.output)}")
    except IOError as e:
        print(f"Error writing dashboard file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
