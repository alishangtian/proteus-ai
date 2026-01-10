"""
Stock Analyzer Core Module
==========================

This module provides the core functionality for stock analysis,
including data acquisition, technical analysis, fundamental analysis,
and trading recommendation generation.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StockAnalyzer:
    """
    Main class for comprehensive stock analysis.
    
    Attributes:
        symbol (str): Stock symbol (e.g., 'AAPL')
        market (str): Market identifier ('US', 'HK', 'CN')
        stock (yfinance.Ticker): yfinance Ticker object
        data (pd.DataFrame): Historical price data
        info (dict): Company information and fundamentals
    """
    
    def __init__(self, symbol, market='US', period='1y', interval='1d'):
        """
        Initialize StockAnalyzer for a specific stock.
        
        Args:
            symbol (str): Stock symbol (e.g., 'AAPL', '0700.HK')
            market (str): Market identifier ('US', 'HK', 'CN')
            period (str): Period for historical data (e.g., '1y', '5y')
            interval (str): Data interval ('1d', '1h', '1wk')
        """
        self.symbol = symbol.upper()
        self.market = market.upper()
        self.period = period
        self.interval = interval
        
        # Format symbol for yfinance based on market
        if market == 'HK':
            self.yf_symbol = f"{symbol}.HK"
        elif market == 'CN':
            # For A-shares, need alternative data source
            self.yf_symbol = f"{symbol}.SS"  # Shanghai
        else:
            self.yf_symbol = symbol
        
        # Initialize yfinance Ticker
        self.stock = yf.Ticker(self.yf_symbol)
        
        # Fetch data
        self.data = None
        self.info = None
        self.fundamentals = None
        
        self._fetch_data()
        self._fetch_info()
    
    def _fetch_data(self):
        """Fetch historical price data."""
        try:
            self.data = self.stock.history(period=self.period, interval=self.interval)
            if self.data.empty:
                raise ValueError(f"No data available for {self.symbol}")
        except Exception as e:
            print(f"Error fetching data for {self.symbol}: {e}")
            # Create empty dataframe with expected columns
            self.data = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    
    def _fetch_info(self):
        """Fetch company information and fundamentals."""
        try:
            self.info = self.stock.info
        except:
            self.info = {}
    
    def get_basic_info(self):
        """
        Get basic stock information.
        
        Returns:
            dict: Basic stock information
        """
        basic_info = {
            'symbol': self.symbol,
            'name': self.info.get('longName', 'N/A'),
            'sector': self.info.get('sector', 'N/A'),
            'industry': self.info.get('industry', 'N/A'),
            'country': self.info.get('country', 'N/A'),
            'market_cap': self.info.get('marketCap', 'N/A'),
            'current_price': self.info.get('currentPrice', 'N/A'),
            '52_week_high': self.info.get('fiftyTwoWeekHigh', 'N/A'),
            '52_week_low': self.info.get('fiftyTwoWeekLow', 'N/A'),
            'dividend_yield': self.info.get('dividendYield', 'N/A'),
            'pe_ratio': self.info.get('trailingPE', 'N/A'),
            'pb_ratio': self.info.get('priceToBook', 'N/A'),
        }
        return basic_info
    
    def calculate_returns(self):
        """
        Calculate various return metrics.
        
        Returns:
            dict: Return metrics
        """
        if self.data.empty:
            return {}
        
        close_prices = self.data['Close']
        
        # Daily returns
        daily_returns = close_prices.pct_change().dropna()
        
        # Cumulative returns
        cumulative_return = (close_prices.iloc[-1] / close_prices.iloc[0] - 1) * 100
        
        # Annualized volatility (assuming 252 trading days)
        if len(daily_returns) > 1:
            annual_volatility = daily_returns.std() * np.sqrt(252) * 100
        else:
            annual_volatility = 0
        
        # Calculate Sharpe ratio (assuming risk-free rate = 0 for simplicity)
        if daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Maximum drawdown
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        return {
            'cumulative_return_pct': round(cumulative_return, 2),
            'annual_volatility_pct': round(annual_volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'avg_daily_return_pct': round(daily_returns.mean() * 100, 3),
            'positive_days_pct': round((daily_returns > 0).sum() / len(daily_returns) * 100, 1)
        }
    
    def calculate_technical_indicators(self):
        """
        Calculate basic technical indicators.
        
        Returns:
            dict: Technical indicators
        """
        if self.data.empty:
            return {}
        
        close_prices = self.data['Close']
        
        # Moving averages
        ma20 = close_prices.rolling(window=20).mean()
        ma50 = close_prices.rolling(window=50).mean()
        ma200 = close_prices.rolling(window=200).mean()
        
        # RSI (Relative Strength Index)
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        bb_middle = close_prices.rolling(window=20).mean()
        bb_std = close_prices.rolling(window=20).std()
        bb_upper = bb_middle + (bb_std * 2)
        bb_lower = bb_middle - (bb_std * 2)
        
        # Current values (latest)
        current_close = close_prices.iloc[-1] if len(close_prices) > 0 else 0
        current_ma20 = ma20.iloc[-1] if len(ma20) > 0 else 0
        current_ma50 = ma50.iloc[-1] if len(ma50) > 0 else 0
        current_ma200 = ma200.iloc[-1] if len(ma200) > 0 else 0
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
        current_bb_upper = bb_upper.iloc[-1] if len(bb_upper) > 0 else 0
        current_bb_lower = bb_lower.iloc[-1] if len(bb_lower) > 0 else 0
        
        # Signal interpretations
        ma_signal = "Bullish" if current_close > current_ma20 > current_ma50 > current_ma200 else "Bearish"
        rsi_signal = "Overbought" if current_rsi > 70 else "Oversold" if current_rsi < 30 else "Neutral"
        bb_position = "Upper Band" if current_close > current_bb_upper else "Lower Band" if current_close < current_bb_lower else "Middle Range"
        
        return {
            'current_price': round(current_close, 2),
            'ma_20': round(current_ma20, 2) if not pd.isna(current_ma20) else 0,
            'ma_50': round(current_ma50, 2) if not pd.isna(current_ma50) else 0,
            'ma_200': round(current_ma200, 2) if not pd.isna(current_ma200) else 0,
            'rsi': round(current_rsi, 1) if not pd.isna(current_rsi) else 50,
            'bb_upper': round(current_bb_upper, 2) if not pd.isna(current_bb_upper) else 0,
            'bb_lower': round(current_bb_lower, 2) if not pd.isna(current_bb_lower) else 0,
            'ma_signal': ma_signal,
            'rsi_signal': rsi_signal,
            'bb_position': bb_position
        }
    
    def analyze_fundamentals(self):
        """
        Analyze fundamental financial metrics.
        
        Returns:
            dict: Fundamental analysis metrics
        """
        fundamentals = {}
        
        # Extract key metrics from info
        metrics = [
            ('trailingPE', 'pe_ratio'),
            ('forwardPE', 'forward_pe'),
            ('priceToBook', 'pb_ratio'),
            ('priceToSalesTrailing12Months', 'ps_ratio'),
            ('enterpriseToRevenue', 'ev_revenue'),
            ('enterpriseToEbitda', 'ev_ebitda'),
            ('profitMargins', 'profit_margin'),
            ('operatingMargins', 'operating_margin'),
            ('returnOnEquity', 'roe'),
            ('returnOnAssets', 'roa'),
            ('debtToEquity', 'debt_equity'),
            ('currentRatio', 'current_ratio'),
            ('quickRatio', 'quick_ratio'),
            ('totalRevenue', 'revenue'),
            ('revenueGrowth', 'revenue_growth'),
            ('earningsGrowth', 'earnings_growth'),
            ('freeCashflow', 'free_cash_flow'),
            ('operatingCashflow', 'operating_cash_flow')
        ]
        
        for yf_key, our_key in metrics:
            value = self.info.get(yf_key)
            if value is not None:
                if isinstance(value, (int, float)):
                    fundamentals[our_key] = round(value, 3)
                else:
                    fundamentals[our_key] = value
        
        # Calculate additional metrics
        if 'revenue' in fundamentals and 'marketCap' in self.info:
            # Market Cap to Revenue
            market_cap = self.info.get('marketCap')
            if market_cap and fundamentals['revenue'] > 0:
                fundamentals['market_cap_to_revenue'] = round(market_cap / fundamentals['revenue'], 2)
        
        return fundamentals
    
    def generate_recommendation(self):
        """
        Generate trading recommendation based on analysis.
        
        Returns:
            dict: Trading recommendation with details
        """
        # Get analysis results
        basic_info = self.get_basic_info()
        returns = self.calculate_returns()
        technicals = self.calculate_technical_indicators()
        fundamentals = self.analyze_fundamentals()
        
        # Initialize scores
        technical_score = 0
        fundamental_score = 0
        risk_score = 0
        
        # Technical scoring (out of 50 points)
        # 1. Price vs moving averages (15 points)
        if technicals.get('ma_signal') == 'Bullish':
            technical_score += 15
        elif technicals.get('ma_signal') == 'Bearish':
            technical_score += 5
        else:
            technical_score += 10
        
        # 2. RSI (10 points)
        rsi = technicals.get('rsi', 50)
        if 30 <= rsi <= 70:
            technical_score += 10  # Neutral is good for entry
        elif rsi < 30:
            technical_score += 8   # Oversold - potential buying opportunity
        else:
            technical_score += 4   # Overbought - caution
        
        # 3. Bollinger Bands position (10 points)
        bb_pos = technicals.get('bb_position')
        if bb_pos == 'Lower Band':
            technical_score += 10  # Near support
        elif bb_pos == 'Middle Range':
            technical_score += 7   # Neutral
        else:
            technical_score += 4   # Near resistance
        
        # 4. Trend strength (15 points)
        cumulative_return = returns.get('cumulative_return_pct', 0)
        if cumulative_return > 10:
            technical_score += 15   # Strong uptrend
        elif cumulative_return > 0:
            technical_score += 10   # Mild uptrend
        elif cumulative_return > -10:
            technical_score += 5    # Mild downtrend
        else:
            technical_score += 0    # Strong downtrend
        
        # Fundamental scoring (out of 50 points)
        # 1. Valuation (15 points)
        pe_ratio = fundamentals.get('pe_ratio')
        if pe_ratio:
            if pe_ratio < 15:
                fundamental_score += 15  # Undervalued
            elif pe_ratio < 25:
                fundamental_score += 10  # Fairly valued
            elif pe_ratio < 40:
                fundamental_score += 5   # Overvalued
            else:
                fundamental_score += 0   # Highly overvalued
        else:
            fundamental_score += 7  # Neutral if no data
        
        # 2. Profitability (10 points)
        profit_margin = fundamentals.get('profit_margin', 0)
        if profit_margin > 0.2:
            fundamental_score += 10   # Highly profitable
        elif profit_margin > 0.1:
            fundamental_score += 7    # Moderately profitable
        elif profit_margin > 0:
            fundamental_score += 4    # Marginally profitable
        else:
            fundamental_score += 0    # Unprofitable
        
        # 3. Growth (10 points)
        revenue_growth = fundamentals.get('revenue_growth', 0)
        if revenue_growth > 0.2:
            fundamental_score += 10   # High growth
        elif revenue_growth > 0.1:
            fundamental_score += 7    # Moderate growth
        elif revenue_growth > 0:
            fundamental_score += 4    # Low growth
        else:
            fundamental_score += 0    # Negative growth
        
        # 4. Financial health (15 points)
        debt_equity = fundamentals.get('debt_equity', 1)
        if debt_equity < 0.5:
            fundamental_score += 15   # Low debt
        elif debt_equity < 1:
            fundamental_score += 10   # Moderate debt
        elif debt_equity < 2:
            fundamental_score += 5    # High debt
        else:
            fundamental_score += 0    # Very high debt
        
        # Risk scoring (negative scale)
        volatility = returns.get('annual_volatility_pct', 0)
        max_drawdown = abs(returns.get('max_drawdown_pct', 0))
        
        # Volatility risk (0 to -25)
        if volatility < 20:
            risk_score = 0
        elif volatility < 30:
            risk_score = -10
        elif volatility < 40:
            risk_score = -15
        else:
            risk_score = -25
        
        # Drawdown risk (0 to -25)
        if max_drawdown < 10:
            risk_score += 0
        elif max_drawdown < 20:
            risk_score += -10
        elif max_drawdown < 30:
            risk_score += -15
        else:
            risk_score += -25
        
        # Total score calculation
        total_score = technical_score + fundamental_score + risk_score
        max_possible = 100  # 50 technical + 50 fundamental
        
        # Determine recommendation
        if total_score >= 70:
            recommendation = 'BUY'
            conviction = 'STRONG'
            rationale = 'Strong technical and fundamental signals with manageable risk'
        elif total_score >= 50:
            recommendation = 'BUY'
            conviction = 'MODERATE'
            rationale = 'Favorable technical or fundamental signals with some risk concerns'
        elif total_score >= 30:
            recommendation = 'HOLD'
            conviction = 'NEUTRAL'
            rationale = 'Mixed signals with balanced risk-reward profile'
        elif total_score >= 10:
            recommendation = 'HOLD'
            conviction = 'CAUTIOUS'
            rationale = 'Weak signals with elevated risk considerations'
        else:
            recommendation = 'SELL'
            conviction = 'MODERATE'
            rationale = 'Poor technical and fundamental signals with high risk'
        
        # Calculate price targets
        current_price = technicals.get('current_price', 0)
        if current_price > 0:
            # Conservative target: 10% above current for BUY, 10% below for SELL
            if recommendation == 'BUY':
                price_target = round(current_price * 1.10, 2)
                stop_loss = round(current_price * 0.90, 2)
            elif recommendation == 'SELL':
                price_target = round(current_price * 0.90, 2)
                stop_loss = round(current_price * 1.10, 2)
            else:  # HOLD
                price_target = round(current_price, 2)
                stop_loss = round(current_price * 0.95, 2)
        else:
            price_target = 0
            stop_loss = 0
        
        return {
            'recommendation': recommendation,
            'conviction': conviction,
            'total_score': total_score,
            'technical_score': technical_score,
            'fundamental_score': fundamental_score,
            'risk_score': risk_score,
            'rationale': rationale,
            'price_target': price_target,
            'stop_loss': stop_loss,
            'time_horizon': '3-6 months',
            'position_sizing': 'Moderate (3-5% of portfolio)' if recommendation == 'BUY' else 'Minimal (1-2%)' if recommendation == 'HOLD' else 'Avoid or Reduce'
        }
    
    def generate_report(self):
        """
        Generate comprehensive analysis report.
        
        Returns:
            dict: Complete analysis report
        """
        report = {
            'basic_info': self.get_basic_info(),
            'returns_analysis': self.calculate_returns(),
            'technical_analysis': self.calculate_technical_indicators(),
            'fundamental_analysis': self.analyze_fundamentals(),
            'trading_recommendation': self.generate_recommendation(),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_period': self.period,
            'data_points': len(self.data) if self.data is not None else 0
        }
        
        return report

# Utility functions
def analyze_stock(symbol, market='US', period='1y'):
    """
    Convenience function to analyze a stock.
    
    Args:
        symbol (str): Stock symbol
        market (str): Market identifier
        period (str): Historical data period
    
    Returns:
        dict: Analysis report
    """
    analyzer = StockAnalyzer(symbol, market, period)
    return analyzer.generate_report()

def compare_stocks(symbols, market='US', period='1y'):
    """
    Compare multiple stocks.
    
    Args:
        symbols (list): List of stock symbols
        market (str): Market identifier
        period (str): Historical data period
    
    Returns:
        dict: Comparative analysis
    """
    results = {}
    for symbol in symbols:
        analyzer = StockAnalyzer(symbol, market, period)
        results[symbol] = {
            'basic_info': analyzer.get_basic_info(),
            'returns': analyzer.calculate_returns(),
            'recommendation': analyzer.generate_recommendation()
        }
    return results
