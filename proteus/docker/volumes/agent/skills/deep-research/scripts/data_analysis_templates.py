"""
Data Analysis Templates for Deep Research

This module provides reusable Python functions for common data analysis tasks
in research projects. These templates can be adapted for specific datasets
and analysis requirements.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Set visualization style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

def load_and_clean_data(filepath, date_column=None):
    """
    Load data from CSV/Excel and perform basic cleaning.
    
    Parameters:
    -----------
    filepath : str
        Path to data file
    date_column : str, optional
        Name of column to parse as dates
    
    Returns:
    --------
    pandas.DataFrame
        Cleaned dataframe
    """
    # Determine file type and load
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    elif filepath.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(filepath)
    else:
        raise ValueError("Unsupported file format. Use CSV or Excel.")
    
    # Parse dates if specified
    if date_column and date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
    
    # Basic cleaning
    df = df.dropna(how='all')  # Remove completely empty rows
    df = df.reset_index(drop=True)
    
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    print(f"Date range: {df[date_column].min()} to {df[date_column].max()}" 
          if date_column and date_column in df.columns else "")
    
    return df

def calculate_growth_rates(df, value_column, date_column, group_column=None):
    """
    Calculate period-over-period growth rates.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    value_column : str
        Column containing values to analyze
    date_column : str
        Date column for time series analysis
    group_column : str, optional
        Column to group by (e.g., product categories)
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame with growth rates
    """
    df = df.copy()
    
    # Ensure date column is datetime and sort
    df[date_column] = pd.to_datetime(df[date_column])
    df = df.sort_values(date_column)
    
    if group_column:
        # Calculate growth rates by group
        growth_rates = []
        for group, group_df in df.groupby(group_column):
            group_df = group_df.sort_values(date_column)
            group_df['period_growth'] = group_df[value_column].pct_change()
            group_df['cumulative_growth'] = (group_df[value_column] / 
                                           group_df[value_column].iloc[0] - 1)
            group_df[group_column] = group
            growth_rates.append(group_df)
        
        result = pd.concat(growth_rates, ignore_index=True)
    else:
        # Calculate overall growth rates
        df = df.sort_values(date_column)
        df['period_growth'] = df[value_column].pct_change()
        df['cumulative_growth'] = (df[value_column] / 
                                 df[value_column].iloc[0] - 1)
        result = df
    
    # Summary statistics
    print("\nGrowth Rate Summary:")
    if group_column:
        for group, group_df in result.groupby(group_column):
            avg_growth = group_df['period_growth'].mean() * 100
            print(f"  {group}: Average period growth = {avg_growth:.2f}%")
    else:
        avg_growth = result['period_growth'].mean() * 100
        print(f"  Average period growth = {avg_growth:.2f}%")
    
    return result

def create_comparison_table(df, compare_column, value_columns, 
                           agg_funcs=['mean', 'median', 'std', 'count']):
    """
    Create comparative analysis table for different groups.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    compare_column : str
        Column to compare across (e.g., categories, regions)
    value_columns : list
        List of numeric columns to analyze
    agg_funcs : list
        Aggregation functions to apply
    
    Returns:
    --------
    pandas.DataFrame
        Comparison table
    """
    comparison_results = {}
    
    for value_col in value_columns:
        # Create pivot table for each value column
        pivot = df.pivot_table(
            values=value_col,
            index=compare_column,
            aggfunc=agg_funcs
        )
        
        # Flatten multi-level columns
        pivot.columns = [f"{value_col}_{func}" for func in agg_funcs]
        comparison_results[value_col] = pivot
    
    # Combine all comparisons
    comparison_table = pd.concat(comparison_results.values(), axis=1)
    
    print(f"\nComparison across {df[compare_column].nunique()} {compare_column} categories")
    print(f"Metrics calculated: {', '.join(agg_funcs)}")
    
    return comparison_table

def plot_time_series(df, date_column, value_columns, 
                    group_column=None, title="Time Series Analysis"):
    """
    Create time series visualization.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    date_column : str
        Date column for x-axis
    value_columns : list
        Columns to plot (can be single or multiple)
    group_column : str, optional
        Column for grouping/faceting
    title : str
        Plot title
    
    Returns:
    --------
    matplotlib.figure.Figure
        Generated figure
    """
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    
    if group_column and len(value_columns) == 1:
        # Multiple lines by group
        fig, ax = plt.subplots(figsize=(14, 8))
        
        for group, group_df in df.groupby(group_column):
            group_df = group_df.sort_values(date_column)
            ax.plot(group_df[date_column], group_df[value_columns[0]], 
                   label=group, linewidth=2)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel(date_column, fontsize=12)
        ax.set_ylabel(value_columns[0], fontsize=12)
        ax.legend(title=group_column)
        ax.grid(True, alpha=0.3)
        
    elif len(value_columns) > 1 and not group_column:
        # Multiple value columns
        fig, axes = plt.subplots(len(value_columns), 1, 
                                figsize=(14, 6*len(value_columns)))
        
        if len(value_columns) == 1:
            axes = [axes]
        
        df = df.sort_values(date_column)
        
        for i, value_col in enumerate(value_columns):
            axes[i].plot(df[date_column], df[value_col], 
                        linewidth=2, color=f'C{i}')
            axes[i].set_title(f'{value_col} over Time', fontsize=14)
            axes[i].set_xlabel(date_column, fontsize=11)
            axes[i].set_ylabel(value_col, fontsize=11)
            axes[i].grid(True, alpha=0.3)
        
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
    else:
        # Simple single line plot
        fig, ax = plt.subplots(figsize=(14, 8))
        df = df.sort_values(date_column)
        ax.plot(df[date_column], df[value_columns[0]], 
               linewidth=2, color='#2E86AB')
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel(date_column, fontsize=12)
        ax.set_ylabel(value_columns[0], fontsize=12)
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def plot_comparison_bar(df, category_column, value_column, 
                       title="Comparison Analysis"):
    """
    Create bar chart for comparison across categories.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    category_column : str
        Column containing categories for x-axis
    value_column : str
        Numeric column for y-axis
    title : str
        Plot title
    
    Returns:
    --------
    matplotlib.figure.Figure
        Generated figure
    """
    # Prepare data
    summary = df.groupby(category_column)[value_column].agg(['mean', 'std', 'count'])
    summary = summary.sort_values('mean', ascending=False)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    bars = ax.bar(range(len(summary)), summary['mean'], 
                 yerr=summary['std'], 
                 capsize=5, 
                 color='#2E86AB', 
                 alpha=0.8)
    
    # Add value labels on bars
    for i, (bar, mean_val) in enumerate(zip(bars, summary['mean'])):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.02 * max(summary['mean']),
                f'{mean_val:.2f}', ha='center', va='bottom', fontsize=10)
    
    ax.set_xlabel(category_column, fontsize=12)
    ax.set_ylabel(value_column, fontsize=12)
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_xticks(range(len(summary)))
    ax.set_xticklabels(summary.index, rotation=45, ha='right')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add count information
    for i, count in enumerate(summary['count']):
        ax.text(i, -0.05 * max(summary['mean']), 
               f'n={count}', ha='center', va='top', fontsize=9, 
               color='gray')
    
    plt.tight_layout()
    return fig

def calculate_correlations(df, numeric_columns, method='pearson'):
    """
    Calculate and visualize correlations between numeric columns.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    numeric_columns : list
        List of numeric column names
    method : str
        Correlation method ('pearson', 'spearman', 'kendall')
    
    Returns:
    --------
    tuple (correlation_matrix, figure)
        Correlation matrix and heatmap visualization
    """
    # Select only numeric columns
    numeric_df = df[numeric_columns].select_dtypes(include=[np.number])
    
    # Calculate correlation matrix
    corr_matrix = numeric_df.corr(method=method)
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=(12, 10))
    
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    cmap = sns.diverging_palette(230, 20, as_cmap=True)
    
    sns.heatmap(corr_matrix, mask=mask, cmap=cmap, center=0,
                square=True, linewidths=.5, 
                cbar_kws={"shrink": .8}, 
                annot=True, fmt='.2f',
                ax=ax)
    
    ax.set_title(f'{method.capitalize()} Correlation Matrix', 
                fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    
    # Print strong correlations
    print("\nStrong Correlations (|r| > 0.7):")
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            corr = corr_matrix.iloc[i, j]
            if abs(corr) > 0.7:
                print(f"  {corr_matrix.columns[i]} ↔ {corr_matrix.columns[j]}: {corr:.3f}")
    
    return corr_matrix, fig

def perform_statistical_test(df, group_column, value_column, test_type='t-test'):
    """
    Perform statistical tests between groups.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    group_column : str
        Column defining groups to compare
    value_column : str
        Numeric column to test
    test_type : str
        Type of test ('t-test', 'mann-whitney', 'anova')
    
    Returns:
    --------
    dict
        Test results and statistics
    """
    from scipy import stats
    import itertools
    
    groups = df[group_column].unique()
    results = {
        'test_type': test_type,
        'groups': list(groups),
        'comparisons': []
    }
    
    if test_type == 't-test' and len(groups) == 2:
        # Independent t-test for two groups
        group1_data = df[df[group_column] == groups[0]][value_column]
        group2_data = df[df[group_column] == groups[1]][value_column]
        
        t_stat, p_value = stats.ttest_ind(group1_data, group2_data, 
                                         nan_policy='omit')
        
        results['statistic'] = t_stat
        results['p_value'] = p_value
        results['significant'] = p_value < 0.05
        
        print(f"\nT-test Results for {value_column}:")
        print(f"  t-statistic: {t_stat:.4f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  Significant at α=0.05: {p_value < 0.05}")
        
    elif test_type == 'anova' and len(groups) > 2:
        # One-way ANOVA for multiple groups
        group_data = [df[df[group_column] == g][value_column] 
                     for g in groups]
        
        f_stat, p_value = stats.f_oneway(*group_data)
        
        results['statistic'] = f_stat
        results['p_value'] = p_value
        results['significant'] = p_value < 0.05
        
        print(f"\nANOVA Results for {value_column}:")
        print(f"  F-statistic: {f_stat:.4f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  Significant at α=0.05: {p_value < 0.05}")
        
        # If significant, perform post-hoc tests
        if p_value < 0.05:
            print("\nPost-hoc pairwise comparisons (Tukey HSD):")
            # Simple pairwise t-tests for demonstration
            for (g1, g2) in itertools.combinations(groups, 2):
                data1 = df[df[group_column] == g1][value_column]
                data2 = df[df[group_column] == g2][value_column]
                _, p_val = stats.ttest_ind(data1, data2, nan_policy='omit')
                print(f"  {g1} vs {g2}: p = {p_val:.4f}")
    
    return results

def generate_research_summary(df, text_column, max_words=100):
    """
    Generate basic text analysis summary for research data.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input dataframe
    text_column : str
        Column containing text data
    max_words : int
        Maximum words for summary
    
    Returns:
    --------
    dict
        Text analysis summary
    """
    from collections import Counter
    import re
    
    # Combine all text
    all_text = ' '.join(df[text_column].astype(str).tolist())
    
    # Basic text cleaning
    words = re.findall(r'\b\w{3,}\b', all_text.lower())
    
    # Word frequency analysis
    word_freq = Counter(words)
    common_words = word_freq.most_common(20)
    
    # Generate summary
    summary = {
        'total_documents': len(df),
        'total_words': len(words),
        'unique_words': len(set(words)),
        'common_words': common_words,
        'avg_words_per_doc': len(words) / len(df) if len(df) > 0 else 0
    }
    
    print(f"\nText Analysis Summary for '{text_column}':")
    print(f"  Total documents: {summary['total_documents']}")
    print(f"  Total words: {summary['total_words']}")
    print(f"  Unique words: {summary['unique_words']}")
    print(f"  Average words per document: {summary['avg_words_per_doc']:.1f}")
    print(f"\nTop 10 most common words:")
    for word, count in common_words[:10]:
        print(f"  {word}: {count}")
    
    return summary

# Example usage function
def example_usage():
    """
    Demonstrate how to use the analysis templates.
    """
    print("Deep Research Data Analysis Templates")
    print("=" * 50)
    print("\nAvailable functions:")
    print("1. load_and_clean_data() - Load and clean data files")
    print("2. calculate_growth_rates() - Calculate growth metrics")
    print("3. create_comparison_table() - Create comparison tables")
    print("4. plot_time_series() - Create time series visualizations")
    print("5. plot_comparison_bar() - Create bar chart comparisons")
    print("6. calculate_correlations() - Calculate and visualize correlations")
    print("7. perform_statistical_test() - Perform statistical tests")
    print("8. generate_research_summary() - Analyze text data")
    print("\nSee function docstrings for detailed usage examples.")

if __name__ == "__main__":
    example_usage()
