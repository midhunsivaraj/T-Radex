import numpy as np

class RiskManager:
    def __init__(self, config):
        self.config = config
        self.daily_pnl = 0
        self.max_daily_loss = config['trading']['max_daily_loss']
        
    def approve_trade(self, signal):
        """Check trade against risk parameters"""
        # Daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            return False
            
        # Add additional risk checks here
        return True
    
    def update_pnl(self, amount):
        """Update running PnL total"""
        self.daily_pnl += amount
        
    def reset_daily_pnl(self):
        """Reset at beginning of new day"""
        self.daily_pnl = 0