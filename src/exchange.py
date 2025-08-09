import ccxt
from datetime import datetime

class ExchangeInterface:
    def __init__(self, config):
        self.config = config
        self.exchange = self._setup_exchange()
    
    def _setup_exchange(self):
        if self.config['exchange']['paper_trading']:
            return PaperExchange()
            
        return ccxt.binance({
            'apiKey': self._get_api_key(),
            'secret': self._get_api_secret(),
            'options': {
                'test': self.config['exchange']['testnet'],
                'adjustForTimeDifference': True
            }
        })
    
    def _get_api_key(self):
        if self.config['exchange']['testnet']:
            return self.config['binance']['testnet_key']
        return self.config['binance']['api_key']
    
    def get_ohlcv(self, symbol, timeframe='1h', limit=100):
        """Get OHLCV data"""
        return pd.DataFrame(
            self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit),
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
    
    def execute_order(self, signal):
        """Execute order based on signal"""
        if self.config['exchange']['paper_trading']:
            return self._simulate_order(signal)
            
        return self.exchange.create_order(
            symbol=signal.symbol,
            type=signal.type,
            side=signal.side,
            amount=signal.amount,
            price=signal.price
        )
    
    def _simulate_order(self, signal):
        """Paper trading simulation"""
        return {
            'id': f"sim-{datetime.now().timestamp()}",
            'symbol': signal.symbol,
            'side': signal.side,
            'amount': signal.amount,
            'price': signal.price or self.get_price(signal.symbol),
            'status': 'filled',
            'pnl': 0  # Will be calculated later
        }

class PaperExchange:
    """Mock exchange for development"""
    def create_order(self, **kwargs):
        print(f"[PAPER TRADE] {kwargs}")
        return {**kwargs, 'id': 'paper-123', 'status': 'filled'}