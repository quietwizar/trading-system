#!/usr/bin/env python3
"""
Plot SPY/RSP Price Ratio and its RSI
"""

import pandas as pd
import matplotlib.pyplot as plt

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Load data
print("Loading SPY and RSP 5-minute data...")
spy_df = pd.read_csv('data/SPY_5Min_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)
rsp_df = pd.read_csv('data/RSP_5Min_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)

# Align
common_dates = spy_df.index.intersection(rsp_df.index)
spy_df = spy_df.loc[common_dates]
rsp_df = rsp_df.loc[common_dates]

# Calculate ratio and RSI
spy_df['ratio'] = spy_df['Close'] / rsp_df['Close']
spy_df['ratio_rsi'] = calculate_rsi(spy_df['ratio'], period=14)

# Drop NaN
spy_df = spy_df.dropna()

print(f"Plotting {len(spy_df)} bars...")

# Create plot with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True)

# Plot 1: SPY/RSP Ratio
ax1.plot(spy_df.index, spy_df['ratio'], linewidth=1, color='blue')
ax1.set_ylabel('SPY/RSP Ratio', fontsize=12)
ax1.set_title('SPY/RSP Price Ratio', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)

# Plot 2: Ratio RSI with trading zones
ax2.plot(spy_df.index, spy_df['ratio_rsi'], linewidth=1.5, color='purple')
ax2.axhline(y=70, color='red', linestyle='--', linewidth=2, label='Overbought (70) - SHORT SPY/LONG RSP')
ax2.axhline(y=30, color='green', linestyle='--', linewidth=2, label='Oversold (30) - LONG SPY/SHORT RSP')
ax2.axhline(y=50, color='gray', linestyle=':', linewidth=1, label='Neutral (50) - Exit Zone')
ax2.fill_between(spy_df.index, 70, 100, alpha=0.2, color='red')
ax2.fill_between(spy_df.index, 0, 30, alpha=0.2, color='green')
ax2.set_ylabel('RSI', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.set_title('RSI of SPY/RSP Ratio (Trading Signals)', fontsize=14, fontweight='bold')
ax2.set_ylim(0, 100)
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

print("\nChart displayed!")
print("\nHow to read:")
print("- RED ZONE (RSI > 70): SPY is overvalued vs RSP → Strategy goes SHORT SPY, LONG RSP")
print("- GREEN ZONE (RSI < 30): RSP is overvalued vs SPY → Strategy goes LONG SPY, SHORT RSP")
print("- GRAY LINE (RSI = 50): Neutral zone where strategy exits positions")
