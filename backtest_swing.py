#!/usr/bin/env python3
"""
SWING TRADING Strategy - Daily bars, longer holds, stable signals
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_sma(prices, period):
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean()

# Load DAILY data
print("Loading SPY and RSP daily data...")
spy_df = pd.read_csv('data/SPY_1Day_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)
rsp_df = pd.read_csv('data/RSP_1Day_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)

# Align dates
common_dates = spy_df.index.intersection(rsp_df.index)
spy_df = spy_df.loc[common_dates]
rsp_df = rsp_df.loc[common_dates]

print(f"Loaded {len(spy_df)} daily bars")

# Calculate indicators
print("Calculating swing trading indicators...")

# 1. Price ratio
spy_df['ratio'] = spy_df['Close'] / rsp_df['Close']

# 2. RSI of ratio (standard 14-day)
spy_df['ratio_rsi'] = calculate_rsi(spy_df['ratio'], period=14)

# 3. Moving averages of ratio for trend
spy_df['ratio_sma20'] = calculate_sma(spy_df['ratio'], 20)
spy_df['ratio_sma50'] = calculate_sma(spy_df['ratio'], 50)

# 4. Z-score of ratio (statistical extremes)
spy_df['ratio_mean60'] = spy_df['ratio'].rolling(60).mean()
spy_df['ratio_std60'] = spy_df['ratio'].rolling(60).std()
spy_df['ratio_zscore'] = (spy_df['ratio'] - spy_df['ratio_mean60']) / spy_df['ratio_std60']

# Drop NaN
spy_df = spy_df.dropna()
rsp_df = rsp_df.loc[spy_df.index]

print(f"Valid data points: {len(spy_df)}")

# SWING STRATEGY PARAMETERS
RSI_OVERBOUGHT = 65
RSI_OVERSOLD = 35
ZSCORE_HIGH = 1.5      # Enter when ratio is 1.5 std devs above mean
ZSCORE_LOW = -1.5      # Enter when ratio is 1.5 std devs below mean
MIN_HOLD_DAYS = 3      # Minimum hold period
MAX_HOLD_DAYS = 20     # Maximum hold period
CAPITAL_USAGE = 0.80   # Use 80% of capital (less aggressive)
STOP_LOSS = 0.04       # 4% stop loss (wider for swing)
PROFIT_TARGET = 0.03   # 3% profit target

# Initialize portfolio
portfolio = {
    'cash': 100000,
    'spy_shares': 0,
    'rsp_shares': 0,
    'equity': [],
    'dates': [],
    'trades': [],
    'entry_value': 0,
    'entry_date': None,
    'days_in_trade': 0
}

current_position = None

print("\nRunning SWING TRADING strategy...")
print(f"Entry: RSI {RSI_OVERBOUGHT}/{RSI_OVERSOLD} + Z-score ±{ZSCORE_HIGH}")
print(f"Hold: {MIN_HOLD_DAYS}-{MAX_HOLD_DAYS} days")
print(f"Profit Target: {PROFIT_TARGET*100}%")
print(f"Stop Loss: {STOP_LOSS*100}%")
print("="*70)

for date in spy_df.index:
    spy_price = spy_df.loc[date, 'Close']
    rsp_price = rsp_df.loc[date, 'Close']
    ratio_rsi = spy_df.loc[date, 'ratio_rsi']
    ratio_zscore = spy_df.loc[date, 'ratio_zscore']
    
    # Calculate portfolio value
    portfolio_value = portfolio['cash'] + \
                      portfolio['spy_shares'] * spy_price + \
                      portfolio['rsp_shares'] * rsp_price
    
    portfolio['equity'].append(portfolio_value)
    portfolio['dates'].append(date)
    
    # Track days in trade
    if current_position is not None:
        portfolio['days_in_trade'] += 1
    
    # Exit logic
    if current_position is not None and portfolio['entry_value'] > 0:
        pnl = portfolio_value - portfolio['entry_value']
        pnl_pct = pnl / portfolio['entry_value']
        days_held = portfolio['days_in_trade']
        
        should_exit = False
        exit_reason = ""
        
        # 1. Profit target
        if pnl_pct >= PROFIT_TARGET:
            should_exit = True
            exit_reason = f"PROFIT TARGET ({pnl_pct*100:.2f}%)"
        
        # 2. Stop loss
        elif pnl_pct <= -STOP_LOSS:
            should_exit = True
            exit_reason = f"STOP LOSS ({pnl_pct*100:.2f}%)"
        
        # 3. Max hold reached
        elif days_held >= MAX_HOLD_DAYS:
            should_exit = True
            exit_reason = f"MAX HOLD ({days_held} days)"
        
        # 4. Mean reversion complete (after minimum hold)
        elif days_held >= MIN_HOLD_DAYS:
            if current_position == 'short_spy_long_rsp':
                if ratio_rsi < 50 and ratio_zscore < 0.5:
                    should_exit = True
                    exit_reason = f"MEAN REVERSION ({days_held} days)"
            elif current_position == 'long_spy_short_rsp':
                if ratio_rsi > 50 and ratio_zscore > -0.5:
                    should_exit = True
                    exit_reason = f"MEAN REVERSION ({days_held} days)"
        
        if should_exit:
            # Close position
            portfolio['cash'] += portfolio['spy_shares'] * spy_price
            portfolio['cash'] += portfolio['rsp_shares'] * rsp_price
            
            portfolio['trades'].append(
                f"{date.date()}: EXIT | {exit_reason} | PnL: ${pnl:.2f} ({pnl_pct*100:.2f}%)"
            )
            
            portfolio['spy_shares'] = 0
            portfolio['rsp_shares'] = 0
            current_position = None
            portfolio['entry_value'] = 0
            portfolio['entry_date'] = None
            portfolio['days_in_trade'] = 0
    
    # Entry logic - only if no position
    if current_position is None:
        position_size = portfolio_value * CAPITAL_USAGE / 2
        
        # ENTRY CONDITION 1: RSI + Z-score both extreme (short SPY/long RSP)
        if ratio_rsi > RSI_OVERBOUGHT and ratio_zscore > ZSCORE_HIGH:
            spy_shares = -(position_size // spy_price)
            rsp_shares = position_size // rsp_price
            
            portfolio['spy_shares'] = spy_shares
            portfolio['rsp_shares'] = rsp_shares
            portfolio['cash'] -= (rsp_shares * rsp_price)
            portfolio['cash'] += (-spy_shares * spy_price)
            portfolio['entry_value'] = portfolio_value
            portfolio['entry_date'] = date
            portfolio['days_in_trade'] = 0
            
            current_position = 'short_spy_long_rsp'
            
            portfolio['trades'].append(
                f"{date.date()}: ENTER SHORT SPY/LONG RSP | RSI={ratio_rsi:.1f}, Z={ratio_zscore:.2f}"
            )
        
        # ENTRY CONDITION 2: RSI + Z-score both extreme (long SPY/short RSP)
        elif ratio_rsi < RSI_OVERSOLD and ratio_zscore < ZSCORE_LOW:
            spy_shares = position_size // spy_price
            rsp_shares = -(position_size // rsp_price)
            
            portfolio['spy_shares'] = spy_shares
            portfolio['rsp_shares'] = rsp_shares
            portfolio['cash'] -= (spy_shares * spy_price)
            portfolio['cash'] += (-rsp_shares * rsp_price)
            portfolio['entry_value'] = portfolio_value
            portfolio['entry_date'] = date
            portfolio['days_in_trade'] = 0
            
            current_position = 'long_spy_short_rsp'
            
            portfolio['trades'].append(
                f"{date.date()}: ENTER LONG SPY/SHORT RSP | RSI={ratio_rsi:.1f}, Z={ratio_zscore:.2f}"
            )

# Results
final_value = portfolio['equity'][-1]
total_pnl = final_value - 100000
entry_trades = len([t for t in portfolio['trades'] if 'ENTER' in t])
profit_exits = len([t for t in portfolio['trades'] if 'PROFIT TARGET' in t])
stop_exits = len([t for t in portfolio['trades'] if 'STOP LOSS' in t])
time_exits = len([t for t in portfolio['trades'] if 'MAX HOLD' in t])
mean_rev_exits = len([t for t in portfolio['trades'] if 'MEAN REVERSION' in t])

print("\n" + "="*70)
print("SWING TRADING RESULTS")
print("="*70)
print(f"Starting Capital: $100,000")
print(f"Final Portfolio Value: ${final_value:,.2f}")
print(f"Total PnL: ${total_pnl:,.2f}")
print(f"Return: {(total_pnl/100000)*100:.2f}%")
print(f"\nTotal Trades: {entry_trades}")
if entry_trades > 0:
    print(f"  Profit Targets: {profit_exits} ({profit_exits/entry_trades*100:.1f}%)")
    print(f"  Stop Losses: {stop_exits} ({stop_exits/entry_trades*100:.1f}%)")
    print(f"  Time Exits: {time_exits} ({time_exits/entry_trades*100:.1f}%)")
    print(f"  Mean Reversions: {mean_rev_exits} ({mean_rev_exits/entry_trades*100:.1f}%)")
print(f"\nAverage P&L per trade: ${total_pnl/max(entry_trades,1):.2f}")
print(f"\nStrategy: Swing (Daily bars, multi-day holds)")
print(f"Signals: RSI {RSI_OVERBOUGHT}/{RSI_OVERSOLD} + Z-score ±{ZSCORE_HIGH}")
print("\nAll Trades:")
for trade in portfolio['trades']:
    print(f"  {trade}")

# Plot
plt.figure(figsize=(14, 7))
plt.plot(portfolio['dates'], portfolio['equity'], linewidth=2)
plt.axhline(y=100000, color='r', linestyle='--', label='Starting Capital')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.title('SWING TRADING Strategy - Daily Bars, Multi-Day Holds')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

print("\n" + "="*70)
