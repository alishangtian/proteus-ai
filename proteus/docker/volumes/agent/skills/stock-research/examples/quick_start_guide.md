# Stock Research Skill - Quick Start Guide

## Installation

1. Ensure you have Python 3.8+ installed
2. Install required dependencies:
   ```bash
   pip install yfinance pandas numpy matplotlib
   ```

## Basic Usage

### Method 1: Using the analyze_stock function
```python
from stock_research import analyze_stock

# Analyze a single stock
report = analyze_stock(symbol="AAPL", market="US", period="1y")
print(f"Recommendation: {report['trading_recommendation']['recommendation']}")
```

### Method 2: Using the StockAnalyzer class
```python
from stock_research import StockAnalyzer

# Create analyzer instance
analyzer = StockAnalyzer(symbol="TSLA", market="US", period="6mo")

# Get specific analysis components
basic_info = analyzer.get_basic_info()
technical = analyzer.calculate_technical_indicators()
fundamentals = analyzer.analyze_fundamentals()
recommendation = analyzer.generate_recommendation()

# Or get complete report
full_report = analyzer.generate_report()
```

### Method 3: Comparing multiple stocks
```python
from stock_research import compare_stocks

# Compare multiple stocks
comparison = compare_stocks(
    symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
    market="US",
    period="1y"
)

for symbol, data in comparison.items():
    print(f"{symbol}: {data['recommendation']['recommendation']}")
```

## Supported Markets

- **US**: US stocks (e.g., "AAPL", "TSLA")
- **HK**: Hong Kong stocks (e.g., "0700.HK" for Tencent)
- **CN**: Chinese A-shares (e.g., "600519.SS" for Kweichow Moutai)

## Available Analysis Components

### 1. Basic Information
- Company name, sector, industry
- Market capitalization
- 52-week range
- Dividend yield

### 2. Return Analysis
- Cumulative returns
- Annual volatility
- Sharpe ratio
- Maximum drawdown

### 3. Technical Analysis
- Moving averages (20, 50, 200-day)
- RSI (Relative Strength Index)
- Bollinger Bands
- Trend signals

### 4. Fundamental Analysis
- Valuation ratios (P/E, P/B, P/S)
- Profitability metrics
- Growth rates
- Financial health indicators

### 5. Trading Recommendation
- Buy/Hold/Sell recommendation
- Conviction level
- Price targets
- Stop loss levels
- Position sizing guidance

## Example: Complete Analysis Pipeline

```python
import json
from stock_research import StockAnalyzer

def analyze_stock_pipeline(symbol, market="US"):
    """Complete analysis pipeline for a stock."""
    
    # Initialize analyzer
    analyzer = StockAnalyzer(symbol, market, period="1y")
    
    # Generate complete report
    report = analyzer.generate_report()
    
    # Extract key insights
    basic = report['basic_info']
    technical = report['technical_analysis']
    fundamental = report['fundamental_analysis']
    recommendation = report['trading_recommendation']
    
    # Print summary
    print(f"\n{symbol} Analysis Summary:")
    print(f"Current Price: ${technical.get('current_price', 'N/A')}")
    print(f"Recommendation: {recommendation.get('recommendation')} "
          f"({recommendation.get('conviction')})")
    print(f"Price Target: ${recommendation.get('price_target', 'N/A')}")
    
    # Save detailed report
    with open(f"{symbol}_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    return report

# Run analysis
report = analyze_stock_pipeline("NVDA")
```

## Customizing Analysis

### Adjusting Analysis Period
```python
# Different time periods available
analyzer = StockAnalyzer("AAPL", period="5d")    # 5 days
analyzer = StockAnalyzer("AAPL", period="1mo")   # 1 month
analyzer = StockAnalyzer("AAPL", period="6mo")   # 6 months
analyzer = StockAnalyzer("AAPL", period="1y")    # 1 year (default)
analyzer = StockAnalyzer("AAPL", period="5y")    # 5 years
```

### Using Different Data Intervals
```python
# Different intervals for technical analysis
analyzer = StockAnalyzer("AAPL", interval="1d")  # Daily (default)
analyzer = StockAnalyzer("AAPL", interval="1h")  # Hourly
analyzer = StockAnalyzer("AAPL", interval="1wk") # Weekly
```

## Visualization

The skill includes basic visualization capabilities. For advanced charts, 
consider using the data with libraries like matplotlib or plotly:

```python
import matplotlib.pyplot as plt

# Plot price history
analyzer.data['Close'].plot(figsize=(12, 6))
plt.title(f"{analyzer.symbol} Price History")
plt.xlabel("Date")
plt.ylabel("Price ($)")
plt.grid(True)
plt.show()
```

## Troubleshooting

### Common Issues

1. **No data available error**
   - Check if market is correct (US, HK, CN)
   - Verify stock symbol is correct
   - Try with different period or interval

2. **Missing fundamental data**
   - Some stocks may not have complete fundamental data
   - Try alternative data sources if needed

3. **API rate limits**
   - yfinance may have rate limits for frequent requests
   - Add delays between requests if analyzing multiple stocks

## Next Steps

1. Explore the templates in the `templates/` directory
2. Check the examples for more advanced usage
3. Customize the analysis logic in `tools/stock_analyzer.py`
4. Extend with additional data sources or indicators

---

For questions or issues, refer to the main SKILL.md documentation.
