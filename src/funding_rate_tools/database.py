import sqlite3
import time
from .config import DATABASE_PATH

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Creates the funding_rates table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS funding_rates (
            symbol TEXT NOT NULL,
            funding_time INTEGER NOT NULL,
            funding_rate REAL NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (symbol, funding_time, source)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS funding_info (
            symbol TEXT NOT NULL,
            interval_hours INTEGER NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (symbol, source)
        )
    ''')
    conn.commit()
    conn.close()

def get_last_funding_time(symbol: str, source: str = None) -> int | None:
    """
    Retrieves the timestamp of the most recent funding rate stored for a given symbol.
    Returns None if no data exists for the symbol.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute('''
            SELECT MAX(funding_time) AS last_time FROM funding_rates WHERE symbol = ? AND source = ?
        ''', (symbol, source))
    else:
        cursor.execute('''
            SELECT MAX(funding_time) AS last_time FROM funding_rates WHERE symbol = ?
        ''', (symbol,))
    row = cursor.fetchone()
    conn.close()
    if row and row['last_time'] is not None:
        return int(row['last_time'])
    return None

def store_funding_rates(symbol: str, rates_data: list[dict], source: str):
    """
    Stores new funding rates in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    prepared_data = [
        (symbol, int(item['fundingTime']), float(item['fundingRate']), source)
        for item in rates_data
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO funding_rates (symbol, funding_time, funding_rate, source)
        VALUES (?, ?, ?, ?)
    ''', prepared_data)
    conn.commit()
    conn.close()

def get_funding_rates(symbol: str, start_time_ms: int, end_time_ms: int = None, source: str = None) -> list[dict]:
    """
    Retrieves funding rates for a symbol within a given time range.
    Timestamps are in milliseconds.
    """
    if end_time_ms is None:
        end_time_ms = int(time.time() * 1000)

    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute('''
            SELECT funding_time, funding_rate FROM funding_rates
            WHERE symbol = ? AND funding_time >= ? AND funding_time <= ? AND source = ?
            ORDER BY funding_time ASC
        ''', (symbol, start_time_ms, end_time_ms, source))
    else:
        cursor.execute('''
            SELECT funding_time, funding_rate FROM funding_rates
            WHERE symbol = ? AND funding_time >= ? AND funding_time <= ?
            ORDER BY funding_time ASC
        ''', (symbol, start_time_ms, end_time_ms))
    rows = cursor.fetchall()
    conn.close()
    return [{"funding_time": r['funding_time'], "funding_rate": r['funding_rate']} for r in rows]

def get_funding_interval_hours(symbol: str, source: str = None) -> int | None:
    conn = get_db_connection()
    if source:
        row = conn.execute(
            'SELECT interval_hours FROM funding_info WHERE symbol = ? AND source = ?', (symbol, source)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT interval_hours FROM funding_info WHERE symbol = ?', (symbol,)
        ).fetchone()
    conn.close()
    return row['interval_hours'] if row else None

def store_funding_info(symbol: str, interval_hours: int, source: str):
    conn = get_db_connection()
    conn.execute(
        'INSERT OR IGNORE INTO funding_info (symbol, interval_hours, source) VALUES (?, ?, ?)',
        (symbol, interval_hours, source)
    )
    conn.commit()
    conn.close()

def get_first_funding_time(symbol: str, source: str = None) -> int | None:
    """
    Retrieves the earliest funding_time stored for a symbol.
    """
    conn = get_db_connection()
    if source:
        row = conn.execute(
            'SELECT MIN(funding_time) AS first_time FROM funding_rates WHERE symbol = ? AND source = ?',
            (symbol, source)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT MIN(funding_time) AS first_time FROM funding_rates WHERE symbol = ?',
            (symbol,)
        ).fetchone()
    conn.close()
    return int(row['first_time']) if row and row['first_time'] is not None else None

# Initialize database on import
setup_database()
