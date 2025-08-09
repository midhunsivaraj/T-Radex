import unittest
from src.bot import TradingBot
from unittest.mock import MagicMock

class TestTradingBot(unittest.TestCase):
    def setUp(self):
        self.bot = TradingBot()
        self.bot.exchange = MagicMock()
        self.bot.risk = MagicMock()
        
    def test_run_loop(self):
        self.bot._analyze_markets = MagicMock(return_value=[])
        self.bot.run()  # Should not raise exceptions
        
    def test_risk_approval(self):
        mock_signal = MagicMock()
        self.bot.risk.approve_trade.return_value = True
        self.bot._execute_trades([mock_signal])
        self.bot.exchange.execute_order.assert_called_once()