#!/usr/bin/env python3
"""
股票分析示例脚本

演示如何使用 yfinance 获取股票数据并进行基础分析
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def analyze_stock(ticker, period="6mo"):
    """分析单只股票"""
    
    print(f"\n分析股票: {ticker}")
    print("=" * 50)
    
    try:
        # 获取股票数据
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty:
            print("无法获取数据")
            return None
            
        # 基本信息
        info = stock.info
        print(f"公司: {info.get('longName', ticker)}")
        print(f"行业: {info.get('industry', 'N/A')}")
        print(f"当前价格: ${hist['Close'].iloc[-1]:.2f}")
        
        # 计算回报率
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        return_pct = ((end_price - start_price) / start_price) * 100
        print(f"{period}回报率: {return_pct:.2f}%")
        
        # 波动率
        daily_returns = hist['Close'].pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100
        print(f"年化波动率: {volatility:.2f}%")
        
        # 简单技术分析
        ma_50 = hist['Close'].rolling(50).mean().iloc[-1]
        ma_200 = hist['Close'].rolling(200).mean().iloc[-1]
        
        print(f"50日MA: ${ma_50:.2f}")
        print(f"200日MA: ${ma_200:.2f}")
        
        if end_price > ma_50 and end_price > ma_200:
            print("趋势: 看涨")
        elif end_price < ma_50 and end_price < ma_200:
            print("趋势: 看跌")
        else:
            print("趋势: 震荡")
            
        return {
            'ticker': ticker,
            'price': end_price,
            'return': return_pct,
            'volatility': volatility,
            'trend': 'bullish' if end_price > ma_50 and end_price > ma_200 else 'bearish'
        }
        
    except Exception as e:
        print(f"错误: {e}")
        return None

def compare_stocks(tickers, period="6mo"):
    """比较多只股票"""
    
    print(f"\n股票比较分析")
    print("=" * 50)
    
    results = []
    for ticker in tickers:
        result = analyze_stock(ticker, period)
        if result:
            results.append(result)
    
    if results:
        print(f"\n{'='*50}")
        print(f"{'股票':<8} {'价格':<10} {'回报率':<10} {'波动率':<10} {'趋势':<10}")
        print(f"{'='*50}")
        
        for r in results:
            print(f"{r['ticker']:<8} ${r['price']:<9.2f} {r['return']:<9.2f}% {r['volatility']:<9.2f}% {r['trend']:<10}")
    
    return results

if __name__ == "__main__":
    # 示例分析
    print("股票分析示例")
    
    # 分析单只股票
    analyze_stock("AAPL", "3mo")
    
    # 比较多只股票
    # compare_stocks(["AAPL", "MSFT", "GOOGL"], "6mo")
    
    print("\n分析完成")
