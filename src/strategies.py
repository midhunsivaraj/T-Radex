import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import talib.abstract as ta
from utils import get_ohlcv_data

@dataclass
class TradeSignal:
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float  # in base currency
    price: float = None  # None for market orders
    type: str = 'limit'  # 'limit' or 'market'
    confidence: float = 1.0  # 0.0 to 1.0

class Strategy:
    def __init__(self, config: Dict):
        self.config = config
        self.min_confidence = config.get('min_confidence', 0.7)
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> List[TradeSignal]:
        """Main analysis method to be implemented by subclasses"""
        raise NotImplementedError
        
    def _validate_signal(self, signal: TradeSignal) -> bool:
        """Ensure signal meets minimum confidence"""
        return signal.confidence >= self.min_confidence

class MeanReversionStrategy(Strategy):
    """Bollinger Band mean reversion strategy"""
    def __init__(self, config: Dict):
        super().__init__(config)
        self.bb_window = config.get('bb_window', 20)
        self.bb_std = config.get('bb_std', 2.0)
        self.rsi_window = config.get('rsi_window', 14)
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> List[TradeSignal]:
        if len(data) < max(self.bb_window, self.rsi_window) * 2:
            return []
            
        # Calculate indicators
        data['upper_bb'], data['middle_bb'], data['lower_bb'] = ta.BBANDS(
            data['close'], 
            timeperiod=self.bb_window,
            nbdevup=self.bb_std,
            nbdevdn=self.bb_std
        )
        data['rsi'] = ta.RSI(data['close'], timeperiod=self.rsi_window)
        
        latest = data.iloc[-1]
        signals = []
        
        # Buy signal: Price touches lower band and RSI < 30
        if latest['close'] <= latest['lower_bb'] and latest['rsi'] < 30:
            signals.append(TradeSignal(
                symbol=symbol,
                side='buy',
                amount=self._calculate_position_size(latest['close']),
                price=latest['close'] * 1.002,  # Slightly above current
                confidence=min(1.0, (30 - latest['rsi']) / 30)  # 0-1 scale
            ))
            
        # Sell signal: Price touches upper band and RSI > 70
        elif latest['close'] >= latest['upper_bb'] and latest['rsi'] > 70:
            signals.append(TradeSignal(
                symbol=symbol,
                side='sell',
                amount=self._calculate_position_size(latest['close']),
                price=latest['close'] * 0.998,  # Slightly below current
                confidence=min(1.0, (latest['rsi'] - 70) / 30)  # 0-1 scale
            ))
            
        return [s for s in signals if self._validate_signal(s)]
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on configured risk"""
        risk_amount = self.config.get('risk_per_trade', 0.01)  # 1% by default
        account_size = self.config.get('account_size', 10000)
        return (account_size * risk_amount) / price

class MomentumStrategy(Strategy):
    """Dual Moving Average Crossover strategy"""
    def __init__(self, config: Dict):
        super().__init__(config)
        self.fast_ma = config.get('fast_ma', 9)
        self.slow_ma = config.get('slow_ma', 21)
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> List[TradeSignal]:
        if len(data) < self.slow_ma * 2:
            return []
            
        # Calculate moving averages
        data['fast_ma'] = ta.SMA(data['close'], timeperiod=self.fast_ma)
        data['slow_ma'] = ta.SMA(data['close'], timeperiod=self.slow_ma)
        
        # Get crossover signals
        data['position'] = np.where(
            data['fast_ma'] > data['slow_ma'], 1, -1)
        data['crossover'] = data['position'].diff()
        
        latest = data.iloc[-1]
        signals = []
        
        # Buy signal: Fast MA crosses above Slow MA
        if latest['crossover'] > 0:
            signals.append(TradeSignal(
                symbol=symbol,
                side='buy',
                amount=self._calculate_position_size(latest['close']),
                type='market',
                confidence=0.8  # Fixed confidence for crossovers
            ))
            
        # Sell signal: Fast MA crosses below Slow MA
        elif latest['crossover'] < 0:
            signals.append(TradeSignal(
                symbol=symbol,
                side='sell',
                amount=self._calculate_position_size(latest['close']),
                type='market',
                confidence=0.8
            ))
            
        return signals

class BreakoutStrategy(Strategy):
    """Support/Resistance Breakout Strategy"""
    def __init__(self, config: Dict):
        super().__init__(config)
        self.resistance_window = config.get('resistance_window', 14)
        self.confirmation_candles = config.get('confirmation_candles', 2)
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> List[TradeSignal]:
        if len(data) < self.resistance_window * 2:
            return []
            
        # Calculate recent resistance and support
        resistance = data['high'].rolling(self.resistance_window).max()
        support = data['low'].rolling(self.resistance_window).min()
        
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        signals = []
        
        # Breakout above resistance with volume confirmation
        if (latest['close'] > resistance[-2] and 
            latest['volume'] > data['volume'].mean()):
            
            # Check if we've closed above resistance for N candles
            confirmed = all(
                data['close'].iloc[-i] > resistance.iloc[-i] 
                for i in range(1, self.confirmation_candles + 1)
            )
            
            if confirmed:
                signals.append(TradeSignal(
                    symbol=symbol,
                    side='buy',
                    amount=self._calculate_position_size(latest['close']),
                    price=resistance[-2] * 1.005,  # 0.5% above resistance
                    confidence=0.9
                ))
                
        # Breakdown below support with volume confirmation
        elif (latest['close'] < support[-2] and 
              latest['volume'] > data['volume'].mean()):
            
            confirmed = all(
                data['close'].iloc[-i] < support.iloc[-i] 
                for i in range(1, self.confirmation_candles + 1)
            )
            
            if confirmed:
                signals.append(TradeSignal(
                    symbol=symbol,
                    side='sell',
                    amount=self._calculate_position_size(latest['close']),
                    price=support[-2] * 0.995,  # 0.5% below support
                    confidence=0.9
                ))
                
        return signals

class StrategyFactory:
    """Creates strategy instances from config"""
    @staticmethod
    def create(config: Dict) -> Strategy:
        strategy_type = config.get('type', 'mean_reversion')
        
        if strategy_type == 'mean_reversion':
            return MeanReversionStrategy(config)
        elif strategy_type == 'momentum':
            return MomentumStrategy(config)
        elif strategy_type == 'breakout':
            return BreakoutStrategy(config)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")