import argparse
import time
from . import binance_api, database
from .database import get_last_funding_time, get_first_funding_time, store_funding_rates, get_funding_interval_hours, store_funding_info
from .hyperliquid_api import fetch_funding_rate_history_hyperliquid
from .bybit_api import fetch_funding_rate_history_bybit, fetch_funding_info_bybit
from .binance_api import fetch_funding_info
from .config import Exchange

def backfill_symbol(symbol: str, delay: int, exchange: Exchange):
    source = exchange.value

    # last_known_time is the latest timestamp known before this script run for this symbol
    last_known_time = get_last_funding_time(symbol)
    print(f"Forward filling {symbol} from {'after ' + str(last_known_time) if last_known_time else 'latest available'}")

    if exchange == Exchange.HYPERLIQUID:
        start_for_forward_fill = last_known_time + 1 if last_known_time is not None else None
    else:
        start_for_forward_fill = last_known_time

    first_forward_pass = True
    while True:
        if exchange == Exchange.HYPERLIQUID:
            rates = fetch_funding_rate_history_hyperliquid(symbol, start_time_ms=start_for_forward_fill)
        elif exchange == Exchange.BYBIT:
            rates = fetch_funding_rate_history_bybit(symbol, start_time_ms=start_for_forward_fill)
        else:  # BINANCE
            rates = binance_api.fetch_funding_rate_history(symbol, start_time_ms=start_for_forward_fill)

        if not rates:
            if first_forward_pass:
                 log_msg_ff = f"  No new rates found for {symbol}"
                 if last_known_time: # This refers to the state *before* this forward-fill attempt
                     log_msg_ff += f" since {last_known_time}."
                 else: # last_known_time was None, meaning DB was empty for this symbol
                     log_msg_ff += " (no prior data, API returned no initial data for forward-fill)."
                 print(log_msg_ff)
            break

        first_forward_pass = False # Forward-fill fetched at least one batch
        store_funding_rates(symbol, rates, source)

        newest_time_in_batch = rates[-1]['fundingTime']
        print(f"  Fetched {len(rates)} new rates for {symbol}, up to {newest_time_in_batch}. Next start for forward-fill: {newest_time_in_batch + 1}")

        if exchange == Exchange.HYPERLIQUID:
            start_for_forward_fill = newest_time_in_batch + 1
        else:
            start_for_forward_fill = newest_time_in_batch
        time.sleep(delay)

    # After forward-fill, determine if and from where to backfill
    first_overall_time_in_db = get_first_funding_time(symbol) # Earliest time in DB *after* potential forward-fill

    boundary_for_backfill = 0
    should_attempt_backfill = False

    if first_overall_time_in_db is not None:
        # Data exists in DB (either pre-existing or added by forward-fill).
        # Backfill from the earliest known point.
        boundary_for_backfill = first_overall_time_in_db
        print(f"Backfilling {symbol} before {boundary_for_backfill}")
        should_attempt_backfill = True
    elif last_known_time is None and first_forward_pass:
        # DB was initially empty for this symbol AND forward-fill (which looks for recent data) found nothing.
        # This implies all data is historical. Start backfill from 'now'.
        boundary_for_backfill = int(time.time() * 1000)
        print(f"No recent data found by forward-fill for new symbol {symbol}. Initiating backfill from current time ({boundary_for_backfill}).")
        should_attempt_backfill = True
    else:
        # All other cases:
        # - DB was empty, forward-fill ran and found something (first_overall_time_in_db would not be None, handled above).
        # - DB had data, forward-fill ran (first_overall_time_in_db would not be None, handled above).
        # This 'else' means no basis to start backfilling under current logic.
        print(f"No data in database for {symbol} to determine a backfill starting point after forward-fill. Skipping backfill.")
        # should_attempt_backfill remains False

    if should_attempt_backfill:
        interval = get_funding_interval_hours(symbol)
        if interval is None:
            # This should ideally be populated by main(), but as a robust fallback:
            default_interval = 8 # Used for both if not found
            print(f"Warning: Funding interval for {symbol} not found in DB. Using default {default_interval}h for backfill step calculation.")
            interval = default_interval

        if exchange == Exchange.HYPERLIQUID:
            chunk = 450
        elif exchange == Exchange.BYBIT:
            chunk = 175
        else:  # BINANCE
            chunk = 900
        ms_step = interval * 3600 * 1000 * chunk

        current_boundary_for_loop = boundary_for_backfill

        while True:
            fetch_chunk_start_time = max(0, current_boundary_for_loop - ms_step)

            if fetch_chunk_start_time >= current_boundary_for_loop:
                 if current_boundary_for_loop == 0 and fetch_chunk_start_time == 0:
                     pass
                 else:
                    print(f"  Backfill for {symbol}: fetch start {fetch_chunk_start_time} is not before current boundary {current_boundary_for_loop}. Stopping.")
                    break

            if exchange == Exchange.HYPERLIQUID:
                rates_chunk = fetch_funding_rate_history_hyperliquid(symbol, start_time_ms=fetch_chunk_start_time)
            elif exchange == Exchange.BYBIT:
                rates_chunk = fetch_funding_rate_history_bybit(symbol, start_time_ms=fetch_chunk_start_time)
            else:  # BINANCE
                rates_chunk = binance_api.fetch_funding_rate_history(symbol, start_time_ms=fetch_chunk_start_time)

            older_rates_in_chunk = [
                r for r in rates_chunk
                if r['fundingTime'] < current_boundary_for_loop and r['fundingTime'] >= fetch_chunk_start_time
            ]

            if not older_rates_in_chunk:
                print(f"  No older rates found for {symbol} before {current_boundary_for_loop} (queried from {fetch_chunk_start_time}).")
                if fetch_chunk_start_time == 0:
                    print(f"  Reached earliest possible data for {symbol} or no data available before {current_boundary_for_loop}.")
                break

            store_funding_rates(symbol, older_rates_in_chunk, source)
            oldest_time_in_this_batch = min(r['fundingTime'] for r in older_rates_in_chunk)
            print(f"  Fetched {len(older_rates_in_chunk)} older rates for {symbol}, back to {oldest_time_in_this_batch}.")

            if oldest_time_in_this_batch == current_boundary_for_loop:
                print(f"  Backfill for {symbol} made no progress from boundary {current_boundary_for_loop}. Stopping.")
                break

            current_boundary_for_loop = oldest_time_in_this_batch

            if current_boundary_for_loop == 0:
                print(f"  Reached timestamp 0 for {symbol}. Stopping backfill.")
                break

            time.sleep(delay)

def main():
    parser = argparse.ArgumentParser(description="Fill missing funding-rate data.")
    parser.add_argument(
        "--symbols", nargs="+", help="Symbols to fill", default=None
    )
    parser.add_argument(
        "--delay", type=int, default=60, help="Seconds between requests"
    )
    parser.add_argument(
        "--exchange",
        choices=["binance", "hyperliquid", "bybit"],
        default="binance",
        help="Exchange to fill data for. Default: binance"
    )
    args = parser.parse_args()
    exchange = Exchange(args.exchange)

    syms_to_process = [s.upper() for s in (args.symbols or database.DEFAULT_SYMBOLS)]

    print("Ensuring funding interval information is available...")
    for symbol_info in syms_to_process:
        if database.get_funding_interval_hours(symbol_info) is None:
            source_for_info = exchange.value
            interval_to_store = None
            if exchange == Exchange.HYPERLIQUID:
                interval_to_store = 8
                print(f"  Storing default funding interval for Hyperliquid symbol {symbol_info}: {interval_to_store} hours.")
            elif exchange == Exchange.BYBIT:
                print(f"  Fetching funding interval for Bybit symbol {symbol_info}...")
                fetched_interval = fetch_funding_info_bybit(symbol_info)
                if fetched_interval:
                    interval_to_store = fetched_interval
                    print(f"  Stored funding interval for {symbol_info}: {interval_to_store} hours.")
                else:
                    print(f"  Could not fetch funding interval for Bybit symbol {symbol_info}. Backfill will use a default if needed.")
            else: # Binance
                print(f"  Fetching funding interval for Binance symbol {symbol_info}...")
                fetched_interval = fetch_funding_info(symbol_info)
                if fetched_interval:
                    interval_to_store = fetched_interval
                    print(f"  Stored funding interval for {symbol_info}: {interval_to_store} hours.")
                else:
                    print(f"  Could not fetch funding interval for Binance symbol {symbol_info}. Backfill will use a default if needed.")

            if interval_to_store:
                database.store_funding_info(symbol_info, interval_to_store, source_for_info)
            time.sleep(0.2) # Small delay if fetching info for multiple symbols

    for s in syms_to_process:
        backfill_symbol(s, args.delay, exchange)

if __name__ == "__main__":
    main()
