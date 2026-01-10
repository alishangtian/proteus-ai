"""
Apple Inc. (AAPL) Analysis Example
===================================

This example demonstrates how to use the Stock Research Skill
to analyze Apple Inc. (AAPL) stock.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stock_analyzer import StockAnalyzer, analyze_stock

def run_aapl_analysis():
    """Complete analysis of AAPL stock."""
    
    print("=" * 60)
    print("APPLE INC. (AAPL) STOCK ANALYSIS")
    print("=" * 60)
    
    # Initialize analyzer
    print("
1. Initializing Stock Analyzer for AAPL...")
    analyzer = StockAnalyzer(symbol="AAPL", market="US", period="1y")
    
    # Get basic information
    print("
2. Basic Company Information:")
    print("-" * 40)
    basic_info = analyzer.get_basic_info()
    
    for key, value in basic_info.items():
        # Format key for display
        display_key = key.replace('_', ' ').title()
        if isinstance(value, (int, float)) and key not in ['symbol', 'name', 'sector', 'industry', 'country']:
            if 'market_cap' in key:
                # Format market cap
                if value >= 1e12:
                    display_value = f"${value/1e12:.2f}T"
                elif value >= 1e9:
                    display_value = f"${value/1e9:.2f}B"
                elif value >= 1e6:
                    display_value = f"${value/1e6:.2f}M"
                else:
                    display_value = f"${value:,.2f}"
            elif 'ratio' in key or 'yield' in key:
                display_value = f"{value:.2f}"
            else:
                display_value = f"${value:,.2f}"
        else:
            display_value = str(value)
        
        print(f"{display_key:25}: {display_value}")
    
    # Calculate returns
    print("
3. Return Metrics:")
    print("-" * 40)
    returns = analyzer.calculate_returns()
    
    for key, value in returns.items():
        display_key = key.replace('_', ' ').title()
        if 'pct' in key:
            display_value = f"{value}%"
        else:
            display_value = f"{value:.2f}"
        print(f"{display_key:25}: {display_value}")
    
    # Technical analysis
    print("
4. Technical Indicators:")
    print("-" * 40)
    technicals = analyzer.calculate_technical_indicators()
    
    tech_display = [
        ('Current Price', 'current_price', '${:.2f}'),
        ('20-Day MA', 'ma_20', '${:.2f}'),
        ('50-Day MA', 'ma_50', '${:.2f}'),
        ('200-Day MA', 'ma_200', '${:.2f}'),
        ('RSI (14)', 'rsi', '{:.1f}'),
        ('Bollinger Upper', 'bb_upper', '${:.2f}'),
        ('Bollinger Lower', 'bb_lower', '${:.2f}'),
        ('MA Signal', 'ma_signal', '{}'),
        ('RSI Signal', 'rsi_signal', '{}'),
        ('BB Position', 'bb_position', '{}')
    ]
    
    for display_name, key, format_str in tech_display:
        if key in technicals:
            value = technicals[key]
            if 'price' in key or 'ma' in key or 'bb' in key:
                formatted = format_str.format(value) if value != 0 else 'N/A'
            else:
                formatted = format_str.format(value) if value != 0 else 'N/A'
            print(f"{display_name:25}: {formatted}")
    
    # Fundamental analysis (selected metrics)
    print("
5. Key Fundamental Metrics:")
    print("-" * 40)
    fundamentals = analyzer.analyze_fundamentals()
    
    fund_display = [
        ('P/E Ratio', 'pe_ratio', '{:.2f}'),
        ('Forward P/E', 'forward_pe', '{:.2f}'),
        ('P/B Ratio', 'pb_ratio', '{:.2f}'),
        ('Profit Margin', 'profit_margin', '{:.2%}'),
        ('ROE', 'roe', '{:.2%}'),
        ('Debt/Equity', 'debt_equity', '{:.2f}'),
        ('Current Ratio', 'current_ratio', '{:.2f}')
    ]
    
    for display_name, key, format_str in fund_display:
        if key in fundamentals:
            value = fundamentals[key]
            if isinstance(value, (int, float)):
                if '%' in format_str:
                    formatted = format_str.format(value)
                else:
                    formatted = format_str.format(value)
                print(f"{display_name:25}: {formatted}")
    
    # Generate recommendation
    print("
6. Trading Recommendation:")
    print("-" * 40)
    recommendation = analyzer.generate_recommendation()
    
    rec_display = [
        ('Recommendation', 'recommendation', '{}'),
        ('Conviction', 'conviction', '{}'),
        ('Total Score', 'total_score', '{}/100'),
        ('Technical Score', 'technical_score', '{}/50'),
        ('Fundamental Score', 'fundamental_score', '{}/50'),
        ('Risk Score', 'risk_score', '{}/50'),
        ('Price Target', 'price_target', '${:.2f}'),
        ('Stop Loss', 'stop_loss', '${:.2f}'),
        ('Time Horizon', 'time_horizon', '{}'),
        ('Position Sizing', 'position_sizing', '{}')
    ]
    
    for display_name, key, format_str in rec_display:
        if key in recommendation:
            value = recommendation[key]
            if 'price' in key:
                formatted = format_str.format(value) if value != 0 else 'N/A'
            else:
                formatted = format_str.format(value)
            print(f"{display_name:25}: {formatted}")
    
    print(f"
Rationale: {recommendation.get('rationale', 'N/A')}")
    
    # Generate complete report
    print("
7. Generating Complete Analysis Report...")
    report = analyzer.generate_report()
    
    # Save report to JSON
    report_file = "aapl_analysis_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"✓ Report saved to: {report_file}")
    
    # Summary
    print("
" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    
    current_price = technicals.get('current_price', 0)
    price_target = recommendation.get('price_target', 0)
    if current_price > 0 and price_target > 0:
        potential_return = ((price_target - current_price) / current_price) * 100
        print(f"
Current Price: ${current_price:.2f}")
        print(f"Price Target: ${price_target:.2f}")
        print(f"Potential Return: {potential_return:+.1f}%")
    
    print(f"
Final Recommendation: {recommendation.get('recommendation')} "
          f"({recommendation.get('conviction')})")
    
    print("
" + "=" * 60)
    print("Analysis completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_aapl_analysis()
