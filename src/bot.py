import time
import yaml
from .exchange import ExchangeInterface
from .risk_manager import RiskManager
from .dashboard import PerformanceDashboard
from .strategies import StrategyFactory

class TradingBot:
    def __init__(self, config_path="config/dev.yaml"):
        self.config = self._load_config(config_path)
        self.exchange = ExchangeInterface(self.config)
        self.risk = RiskManager(self.config)
        self.dashboard = PerformanceDashboard()
        self.strategies = [
            StrategyFactory.create(s) 
            for s in self.config.get('strategies', [])
        ]
        
    def _load_config(self, path):
        with open(path) as f:
            config = yaml.safe_load(f)
        with open("config/secrets.yaml") as f:
            secrets = yaml.safe_load(f)
        return {**config, **secrets}
    
    def run(self):
        """Main trading loop"""
        while True:
            signals = self._analyze_markets()
            self._execute_trades(signals)
            time.sleep(self.config['app']['update_interval'])
    
    def _analyze_markets(self):
        """Generate trading signals from all strategies"""
        signals = []
        for symbol in self.config.get('watchlist', ['BTC/USDT']):
            data = self.exchange.get_ohlcv(symbol, '1h', limit=100)
            for strategy in self.strategies:
                signals.extend(strategy.analyze(symbol, data))
        return signals
    
    def _execute_trades(self, signals):
        """Process trade signals with risk checks"""
        for signal in signals:
            if self.risk.approve_trade(signal):
                order = self.exchange.execute_order(signal)
                self.dashboard.record_trade(order)
                self.risk.update_pnl(order.get('pnl', 0))

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()