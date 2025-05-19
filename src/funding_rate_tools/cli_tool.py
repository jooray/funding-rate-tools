import argparse
import sys
import time
from datetime import datetime, timezone
import json # Added for JSON output

from . import config, database, binance_api, calculations
from .database import get_funding_interval_hours, store_funding_info, store_funding_rates
from .binance_api import fetch_funding_info
from .hyperliquid_api import fetch_funding_rate_history_hyperliquid

def main():
    """Main function for the CLI tool."""
    parser = argparse.ArgumentParser(description="Fetch Binance funding rates and calculate P.A. rates.")
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
        "--verbose",
        action="store_true",
        help="Print all debug and info messages."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as a JSON map (pair to numeric p.a. rate)."
    )
    parser.add_argument(
        "--exchange",
        choices=["binance", "hyperliquid"],
        default="binance",
        help="Exchange to fetch funding rates from. Default: binance"
    )

    period_group = parser.add_mutually_exclusive_group(required=True)
    period_group.add_argument("--last-day", action="store_true", help="Calculate P.A. rate for the last 24 hours.")
    period_group.add_argument("--last-week", action="store_true", help="Calculate P.A. rate for the last 7 days.")
    period_group.add_argument("--last-month", action="store_true", help="Calculate P.A. rate for the last 30 days.")
    period_group.add_argument("--since", type=str, help="Calculate P.A. rate since a specific date (YYYY-MM-DD).", metavar="YYYY-MM-DD")

    args = parser.parse_args()
    use_hl = args.exchange == "hyperliquid"

    # Helper for verbose printing
    def v_print(message):
        if args.verbose:
            print(message)

    symbols = [s.upper() for s in args.symbols]
    refresh_failed_for_any = False

    if not args.no_refresh:
        v_print("Refreshing data...")
        for symbol in symbols:
            # ensure funding-interval is stored
            if get_funding_interval_hours(symbol) is None:
                source = "hyperliquid" if use_hl else "binance"
                if use_hl:
                    store_funding_info(symbol, 8, source)
                else:
                    hrs = fetch_funding_info(symbol)
                    if hrs:
                        store_funding_info(symbol, hrs, source)

            v_print(f"Fetching data for {symbol}...")
            last_time_ms = database.get_last_funding_time(symbol)
            fetch_start_time = last_time_ms + 1 if last_time_ms else None

            try:
                source = "hyperliquid" if use_hl else "binance"
                new_rates = (
                    fetch_funding_rate_history_hyperliquid(symbol, start_time_ms=fetch_start_time)
                    if use_hl
                    else binance_api.fetch_funding_rate_history(symbol, start_time_ms=fetch_start_time)
                )
                if new_rates:
                    store_funding_rates(symbol, new_rates, source)
                    v_print(f"Stored {len(new_rates)} new rate(s) for {symbol}.")
                else:
                    v_print(f"No new rates found for {symbol} since last fetch or API returned no data.")
            except Exception as e:
                v_print(f"Error refreshing data for {symbol}: {e}")
                refresh_failed_for_any = True
            time.sleep(0.5)

    results_numeric = {}
    results_display = {}
    calculation_possible_for_any = False

    start_time_ms = calculations.get_start_time_for_cli_period(args)
    if start_time_ms is None and args.since:
        if args.json:
            print(json.dumps({"error": "Invalid date format for --since. Use YYYY-MM-DD."}))
        else:
            print("Error: Invalid date format for --since. Use YYYY-MM-DD.")
        sys.exit(1)

    end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for symbol in symbols:
        rates_data = database.get_funding_rates(symbol, start_time_ms, end_time_ms)
        if not rates_data:
            results_numeric[symbol] = None
            results_display[symbol] = "N/A (Insufficient data for period)"
            continue

        # pass symbol into pa calculation
        pa_rate = calculations.calculate_pa_rate(symbol, rates_data)
        if pa_rate is not None:
            results_numeric[symbol] = round(pa_rate, 2)
            results_display[symbol] = f"{pa_rate:.2f}% p.a." # Added space
            calculation_possible_for_any = True
        else:
            results_numeric[symbol] = None
            results_display[symbol] = "N/A (Calculation error)"

    if args.json:
        output_json = {}
        for symbol in symbols:
            output_json[symbol] = results_numeric[symbol] # Store None if not calculable
        print(json.dumps(output_json))
    elif len(symbols) == 1:
        symbol = symbols[0]
        if results_numeric[symbol] is not None:
            print(results_numeric[symbol]) # Print only number for single pair
        else:
            print(results_display[symbol]) # Print N/A message
            if refresh_failed_for_any:
                 sys.exit(1) # Still exit with error if refresh failed
    else: # Multiple pairs, non-JSON
        for symbol in symbols:
            print(f"{symbol}: {results_display[symbol]}")

    if refresh_failed_for_any:
        sys.exit(1)
    if not calculation_possible_for_any and not args.json : # if json, it already printed
        # if no calculation was possible for any pair, and not json output
        # (json output handles its own error state via nulls)
        # and we are not printing single pair (which has its own N/A)
        if len(symbols) > 1:
             v_print("No calculations were possible for the requested pairs and period.")
        sys.exit(1) # Exit with error if no calculation was possible for any pair

    sys.exit(0)

if __name__ == "__main__":
    main()
