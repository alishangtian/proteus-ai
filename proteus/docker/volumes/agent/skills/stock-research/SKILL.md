---
name: stock-research
description: Comprehensive toolkit for stock analysis, research, and trading recommendations. Provides data acquisition, technical analysis, fundamental analysis, risk assessment, and professional reporting for stocks.
license: MIT
---

# Stock Research Skill

This skill provides a comprehensive framework for conducting in-depth stock analysis and generating trading recommendations. It integrates data acquisition, technical analysis, fundamental analysis, risk assessment, and professional reporting to support investment decision-making.

## Purpose

To empower users with systematic approaches to stock research that go beyond surface-level information. This skill helps:
- Collect and analyze real-time and historical stock data
- Perform technical analysis using various indicators and patterns
- Conduct fundamental analysis of company financials and valuations
- Assess investment risks and calculate risk-adjusted returns
- Generate structured research reports with actionable trading recommendations
- Visualize stock data through charts and technical indicators

## Core Principles

### 1. Data-Driven Analysis
- Base all analysis on reliable financial data from multiple sources
- Verify data accuracy through cross-referencing and validation
- Use statistical methods to identify meaningful patterns

### 2. Multi-Dimensional Analysis
- Combine technical, fundamental, and sentiment analysis
- Consider both quantitative metrics and qualitative factors
- Analyze stocks from multiple timeframes (short, medium, long-term)

### 3. Risk-Aware Decision Making
- Quantify investment risks using standard financial metrics
- Calculate risk-adjusted returns (Sharpe ratio, Sortino ratio)
- Provide clear risk disclosures and limitations

### 4. Structured Reporting
- Present findings in a clear, logical structure suitable for investors
- Include executive summaries, key findings, and actionable recommendations
- Use visualizations to enhance understanding of complex data

## Core Components

### 1. Data Acquisition Module
- **Real-time Data**: Fetch current stock prices, volume, and market data
- **Historical Data**: Retrieve historical price data with adjustable timeframes
- **Fundamental Data**: Access financial statements, ratios, and company information
- **Market Data**: Obtain sector/industry comparisons and benchmark indices

### 2. Technical Analysis Module
- **Price Action**: Support/resistance levels, trend analysis, chart patterns
- **Indicators**: Moving averages, RSI, MACD, Bollinger Bands, Stochastic Oscillator
- **Volume Analysis**: Volume trends, OBV (On-Balance Volume)
- **Volatility Measures**: ATR (Average True Range), standard deviation

### 3. Fundamental Analysis Module
- **Financial Statements**: Income statement, balance sheet, cash flow analysis
- **Valuation Metrics**: P/E ratio, P/B ratio, EV/EBITDA, dividend yield
- **Profitability Ratios**: ROE, ROA, gross margin, operating margin
- **Growth Metrics**: Revenue growth, earnings growth, future estimates

### 4. Risk Assessment Module
- **Volatility Analysis**: Historical and implied volatility
- **Drawdown Analysis**: Maximum drawdown, recovery periods
- **Correlation Analysis**: Sector and market correlations
- **Scenario Analysis**: Best-case/worst-case scenarios

### 5. Trading Recommendation Module
- **Recommendation Framework**: Buy/Hold/Sell with conviction levels
- **Price Targets**: Based on technical and fundamental analysis
- **Risk Management**: Stop-loss levels, position sizing suggestions
- **Timing Considerations**: Entry/exit timing based on technical signals

## Usage Instructions

### Basic Usage Pattern
```python
# Example: Analyze a stock and generate report
from stock_research import StockAnalyzer

# Initialize analyzer for a stock
analyzer = StockAnalyzer(symbol="AAPL", market="US")

# Get comprehensive analysis
report = analyzer.analyze(
    timeframe="1y",
    include_technical=True,
    include_fundamental=True,
    include_risk=True
)

# Generate trading recommendation
recommendation = analyzer.get_recommendation()

# Export report
analyzer.export_report(format="html")
```

### Step-by-Step Workflow

1. **Stock Selection & Data Collection**
   - Specify stock symbol and market
   - Collect real-time and historical price data
   - Gather fundamental financial data

2. **Technical Analysis**
   - Calculate key technical indicators
   - Identify chart patterns and trends
   - Analyze volume and momentum

3. **Fundamental Analysis**
   - Review financial statements and ratios
   - Compare with industry peers
   - Assess valuation metrics

4. **Risk Assessment**
   - Calculate volatility and drawdown metrics
   - Assess market and sector risks
   - Evaluate risk-adjusted returns

5. **Integration & Synthesis**
   - Combine technical and fundamental insights
   - Weight factors based on investment timeframe
   - Identify key catalysts and risks

6. **Recommendation Generation**
   - Determine Buy/Hold/Sell recommendation
   - Set price targets and stop-loss levels
   - Provide position sizing guidance

7. **Report Generation**
   - Create structured research report
   - Include charts and visualizations
   - Present clear investment thesis

## Available Tools

### Data Sources
- **yfinance**: Primary source for US and global stocks
- **akshare**: Alternative for Chinese stocks (A-shares)
- **Alpha Vantage**: For alternative data and extended history
- **IEX Cloud**: For real-time US stock data

### Analysis Libraries
- **TA-Lib**: Technical analysis library with 150+ indicators
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computations
- **scipy**: Statistical analysis

### Visualization
- **matplotlib**: Basic charting and plotting
- **plotly**: Interactive charts and dashboards
- **mplfinance**: Financial charts with candlestick patterns

## Templates

The `templates/` directory contains:
- **Stock Research Report Template**: Standardized structure for comprehensive stock analysis reports
- **Technical Analysis Template**: Framework for technical indicator analysis
- **Fundamental Analysis Template**: Template for financial statement analysis
- **Trading Recommendation Template**: Format for presenting trading recommendations
- **Risk Assessment Template**: Framework for evaluating investment risks

## Examples

The `examples/` directory contains:
- **AAPL Analysis Example**: Complete analysis of Apple Inc.
- **TSLA Technical Analysis**: Technical analysis of Tesla stock
- **MSFT Fundamental Analysis**: Fundamental analysis of Microsoft
- **Portfolio Risk Assessment**: Example of multi-stock risk analysis

## Quality Standards

All stock research outputs should meet these criteria:

1. **Completeness**: Cover technical, fundamental, and risk dimensions
2. **Accuracy**: Use verified data sources and correct calculations
3. **Transparency**: Clearly state assumptions and limitations
4. **Actionability**: Provide specific, actionable recommendations
5. **Risk Awareness**: Include appropriate risk disclosures

## Limitations & Disclaimers

- **Data Limitations**: Free data sources may have delays or limitations
- **Market Risk**: All investments carry risk of loss
- **Past Performance**: Historical performance does not guarantee future results
- **Not Financial Advice**: Outputs are for informational purposes only

---

*This skill is designed to complement Proteus AI's research capabilities by providing specialized tools and frameworks for systematic stock analysis and investment research.*
