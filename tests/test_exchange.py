import unittest
from src.exchange import ExchangeInterface
from unittest.mock import patch

class TestExchange(unittest.TestCase):
    @patch('ccxt.binance')
    def test_live_exchange(self, mock_binance):
        exchange = ExchangeInterface({
            'exchange': {'testnet': False, 'paper_trading': False},
            'binance': {'api_key': 'test', 'api_secret': 'test'}
        })
        self.assertIsNotNone(exchange.exchange)