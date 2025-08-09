import time
from typing import List, Dict, Any
import pandas as pd

def get_ohlcv_data(exchange, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """Fetch OHLCV data from exchange"""
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    return pd.DataFrame(
        data, 
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )

def calculate_pnl(entry_price: float, exit_price: float, amount: float) -> float:
    """Calculate profit/loss for a trade"""
    return (exit_price - entry_price) * amount

def format_price(price: float) -> str:
    """Format price with appropriate decimals"""
    if price >= 1:
        return f"{price:.2f}"
    return f"{price:.8f}".rstrip('0').rstrip('.')