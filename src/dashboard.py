import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import webbrowser
from pathlib import Path

class PerformanceDashboard:
    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self._init_db()
        
    def _init_db(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                amount REAL NOT NULL,
                entry_time DATETIME NOT NULL,
                exit_time DATETIME,
                fee REAL DEFAULT 0,
                pnl REAL,
                pnl_percent REAL,
                strategy TEXT,
                tags TEXT
            )
            """)
            
            # Create indexes for faster queries
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol)
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_time ON trades (entry_time)
            """)

    def record_trade(self, trade: Dict) -> None:
        """Record a completed trade"""
        required_fields = {'id', 'symbol', 'side', 'entry_price', 'amount'}
        if not all(field in trade for field in required_fields):
            raise ValueError(f"Missing required fields: {required_fields - trade.keys()}")

        # Calculate PnL if exit_price provided
        pnl = None
        pnl_percent = None
        if 'exit_price' in trade:
            pnl = (trade['exit_price'] - trade['entry_price']) * trade['amount']
            pnl_percent = ((trade['exit_price'] / trade['entry_price']) - 1) * 100

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT OR REPLACE INTO trades VALUES (
                :id, :symbol, :side, :entry_price, :exit_price, :amount,
                :entry_time, :exit_time, :fee, :pnl, :pnl_percent, :strategy, :tags
            )
            """, {
                'id': trade['id'],
                'symbol': trade['symbol'],
                'side': trade['side'],
                'entry_price': trade['entry_price'],
                'exit_price': trade.get('exit_price'),
                'amount': trade['amount'],
                'entry_time': trade.get('entry_time', datetime.now()),
                'exit_time': trade.get('exit_time'),
                'fee': trade.get('fee', 0),
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'strategy': trade.get('strategy'),
                'tags': ','.join(trade.get('tags', []))
            })
            conn.commit()

    def get_trades(self, days: int = 30) -> pd.DataFrame:
        """Get recent trades as DataFrame"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql("""
                SELECT * FROM trades 
                WHERE entry_time >= ?
                ORDER BY entry_time DESC
            """, conn, params=(datetime.now() - timedelta(days=days),)
        
        # Convert columns to proper types
        if not df.empty:
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df['duration'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 3600
        return df

    def generate_report(self) -> Dict:
        """Generate comprehensive performance report"""
        df = self.get_trades(90)  # Last 90 days
        
        if df.empty:
            return {"error": "No trades found"}
        
        # Key metrics
        metrics = {
            'total_trades': len(df),
            'winning_trades': len(df[df['pnl'] > 0]),
            'losing_trades': len(df[df['pnl'] < 0]),
            'win_rate': len(df[df['pnl'] > 0]) / len(df) * 100,
            'total_pnl': df['pnl'].sum(),
            'avg_pnl': df['pnl'].mean(),
            'max_drawdown': df['pnl'].cumsum().min(),
            'profit_factor': abs(df[df['pnl'] > 0]['pnl'].sum() / 
                            df[df['pnl'] < 0]['pnl'].sum())
        }

        # Strategy performance
        strategy_stats = df.groupby('strategy').agg({
            'pnl': ['count', 'sum', 'mean'],
            'pnl_percent': 'mean'
        }).sort_values(('pnl', 'sum'), ascending=False)

        # Create visualizations
        figures = {
            'cumulative_pnl': self._create_cumulative_pnl_chart(df),
            'daily_pnl': self._create_daily_pnl_chart(df),
            'strategy_performance': self._create_strategy_chart(strategy_stats),
            'win_loss_distribution': self._create_win_loss_chart(df)
        }

        return {
            'metrics': metrics,
            'strategy_stats': strategy_stats.to_dict(),
            'figures': figures
        }

    def _create_cumulative_pnl_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create cumulative PnL chart"""
        fig = px.line(
            df.sort_values('entry_time'),
            x='entry_time',
            y=df['pnl'].cumsum(),
            title='Cumulative Profit/Loss Over Time',
            labels={'entry_time': 'Date', 'y': 'Cumulative PnL (USD)'}
        )
        fig.update_traces(line=dict(width=3))
        fig.update_layout(hovermode='x unified')
        return fig

    def _create_daily_pnl_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create daily PnL histogram"""
        df['date'] = df['entry_time'].dt.date
        daily = df.groupby('date')['pnl'].sum().reset_index()
        
        fig = px.bar(
            daily,
            x='date',
            y='pnl',
            title='Daily Profit/Loss',
            color=np.where(daily['pnl'] >= 0, 'Win', 'Loss'),
            color_discrete_map={'Win': '#3D9970', 'Loss': '#FF4136'}
        )
        fig.update_layout(bargap=0.1)
        return fig

    def _create_strategy_chart(self, stats: pd.DataFrame) -> go.Figure:
        """Create strategy performance chart"""
        fig = px.bar(
            stats.reset_index(),
            x='strategy',
            y=('pnl', 'sum'),
            title='Strategy Performance (Total PnL)',
            color=('pnl_percent', 'mean'),
            color_continuous_scale='Tealrose'
        )
        fig.update_layout(coloraxis_colorbar=dict(title='Avg % Return'))
        return fig

    def _create_win_loss_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create win/loss distribution chart"""
        fig = px.box(
            df,
            x='strategy',
            y='pnl_percent',
            title='Win/Loss Distribution by Strategy',
            points='all'
        )
        fig.update_traces(boxmean=True)
        return fig

    def show_dashboard(self, open_browser: bool = True) -> str:
        """Generate and display interactive dashboard"""
        report = self.generate_report()
        
        if 'error' in report:
            return report['error']
            
        # Create HTML dashboard
        html = self._create_html_report(report)
        dashboard_path = Path(self.db_path).parent / 'dashboard.html'
        
        with open(dashboard_path, 'w') as f:
            f.write(html)
            
        if open_browser:
            webbrowser.open(f'file://{dashboard_path.absolute()}')
            
        return str(dashboard_path)

    def _create_html_report(self, report: Dict) -> str:
        """Generate complete HTML dashboard"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trading Performance Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
                .metric-card {{ 
                    background: #f8f9fa; border-radius: 5px; padding: 15px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;
                }}
                .metric-value {{ font-size: 24px; font-weight: bold; margin: 5px 0; }}
                .chart {{ margin: 30px 0; height: 400px; }}
                .positive {{ color: #3D9970; }}
                .negative {{ color: #FF4136; }}
            </style>
        </head>
        <body>
            <h1>Trading Performance Dashboard</h1>
            <h2>{datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
            
            <div class="metrics">
                <div class="metric-card">
                    <div>Total Trades</div>
                    <div class="metric-value">{report['metrics']['total_trades']}</div>
                </div>
                <div class="metric-card">
                    <div>Win Rate</div>
                    <div class="metric-value">{report['metrics']['win_rate']:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div>Total PnL</div>
                    <div class="metric-value {'positive' if report['metrics']['total_pnl'] >= 0 else 'negative'}">
                        ${report['metrics']['total_pnl']:,.2f}
                    </div>
                </div>
                <div class="metric-card">
                    <div>Profit Factor</div>
                    <div class="metric-value">{report['metrics']['profit_factor']:.2f}</div>
                </div>
            </div>
            
            <div class="chart" id="cumulative_pnl"></div>
            <div class="chart" id="daily_pnl"></div>
            <div class="chart" id="strategy_performance"></div>
            <div class="chart" id="win_loss_distribution"></div>
            
            <script>
                Plotly.react('cumulative_pnl', {report['figures']['cumulative_pnl'].to_json()}, {{}});
                Plotly.react('daily_pnl', {report['figures']['daily_pnl'].to_json()}, {{}});
                Plotly.react('strategy_performance', {report['figures']['strategy_performance'].to_json()}, {{}});
                Plotly.react('win_loss_distribution', {report['figures']['win_loss_distribution'].to_json()}, {{}});
            </script>
        </body>
        </html>
        """

if __name__ == "__main__":
    dashboard = PerformanceDashboard()
    dashboard.show_dashboard()