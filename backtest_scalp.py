#!/usr/bin/env python3
"""
HYPER-SHORT Scalping Strategy - Quick in, quick out
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

# Load 5-minute data
print("Loading SPY and RSP 5-minute data...")
spy_df = pd.read_csv('data/SPY_5Min_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)
rsp_df = pd.read_csv('data/RSP_5Min_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)

# Align dates
common_dates = spy_df.index.intersection(rsp_df.index)
spy_df = spy_df.loc[common_dates]
rsp_df = rsp_df.loc[common_dates]

print(f"Loaded {len(spy_df)} 5-minute bars")

# Calculate ratio and RSI
print("Calculating SPY/RSP ratio and RSI...")
spy_df['ratio'] = spy_df['Close'] / rsp_df['Close']
spy_df['ratio_rsi'] = calculate_rsi(spy_df['ratio'], period=14)

# Drop NaN
valid_idx = spy_df['ratio_rsi'].notna()
spy_df = spy_df[valid_idx]
rsp_df = rsp_df[valid_idx]

print(f"Valid data points: {len(spy_df)}")

# HYPER-SHORT STRATEGY PARAMETERS
RSI_OVERBOUGHT = 65  # More sensitive (was 70)
RSI_OVERSOLD = 35    # More sensitive (was 30)
CAPITAL_USAGE = 0.90
MAX_HOLD_BARS = 12   # Maximum 12 bars = 60 minutes
PROFIT_TARGET = 0.005  # 0.5% profit target
STOP_LOSS = 0.003     # 0.3% stop loss

# Initialize portfolio
portfolio = {
    'cash': 100000,
    'spy_shares': 0,
    'rsp_shares': 0,
    'equity': [],
    'dates': [],
    'trades': [],
    'entry_value': 0,
    'entry_bar': 0
}

current_position = None
bars_in_position = 0

print("\nRunning HYPER-SHORT scalping strategy...")
print(f"RSI Thresholds: {RSI_OVERBOUGHT}/{RSI_OVERSOLD} (tighter)")
print(f"Max Hold: {MAX_HOLD_BARS} bars (60 minutes)")
print(f"Profit Target: {PROFIT_TARGET*100}%")
print(f"Stop Loss: {STOP_LOSS*100}%")
print("="*60)

bar_count = 0

for date in spy_df.index:
    bar_count += 1
    spy_price = spy_df.loc[date, 'Close']
    rsp_price = rsp_df.loc[date, 'Close']
    ratio_rsi = spy_df.loc[date, 'ratio_rsi']
    
    # Calculate portfolio value
    portfolio_value = portfolio['cash'] + \
                      portfolio['spy_shares'] * spy_price + \
                      portfolio['rsp_shares'] * rsp_price
    
    portfolio['equity'].append(portfolio_value)
    portfolio['dates'].append(date)
    
    # If in position, check exit conditions
    if current_position is not None:
        bars_in_position += 1
        position_pnl = portfolio_value - portfolio['entry_value']
        pnl_pct = position_pnl / portfolio['entry_value']
        
        should_exit = False
        exit_reason = ""
        
        # 1. Profit target hit
        if pnl_pct >= PROFIT_TARGET:
            should_exit = True
            exit_reason = f"PROFIT TARGET ({pnl_pct*100:.2f}%)"
        
        # 2. Stop loss hit
        elif pnl_pct <= -STOP_LOSS:
            should_exit = True
            exit_reason = f"STOP LOSS ({pnl_pct*100:.2f}%)"
        
        # 3. Time limit reached
        elif bars_in_position >= MAX_HOLD_BARS:
            should_exit = True
            exit_reason = f"TIME LIMIT ({bars_in_position} bars)"
        
        # 4. RSI mean reversion (original exit)
        elif current_position == 'short_spy_long_rsp' and ratio_rsi < 50:
            should_exit = True
            exit_reason = f"RSI REVERSION ({ratio_rsi:.1f})"
        elif current_position == 'long_spy_short_rsp' and ratio_rsi > 50:
            should_exit = True
            exit_reason = f"RSI REVERSION ({ratio_rsi:.1f})"
        
        if should_exit:
            # Close position
            portfolio['cash'] += portfolio['spy_shares'] * spy_price
            portfolio['cash'] += portfolio['rsp_shares'] * rsp_price
            
            portfolio['trades'].append(
                f"{date}: CLOSE | {exit_reason} | Held {bars_in_position} bars | PnL: ${position_pnl:.2f}"
            )
            
            portfolio['spy_shares'] = 0
            portfolio['rsp_shares'] = 0
            current_position = None
            bars_in_position = 0
            portfolio['entry_value'] = 0
    
    # Entry logic
    if current_position is None:
        position_size = portfolio_value * CAPITAL_USAGE / 2
        
        if ratio_rsi > RSI_OVERBOUGHT:
            # Short SPY, Long RSP
            spy_shares = -(position_size // spy_price)
            rsp_shares = position_size // rsp_price
            
            portfolio['spy_shares'] = spy_shares
            portfolio['rsp_shares'] = rsp_shares
            portfolio['cash'] -= (rsp_shares * rsp_price)
            portfolio['cash'] += (-spy_shares * spy_price)
            portfolio['entry_value'] = portfolio_value
            portfolio['entry_bar'] = bar_count
            
            current_position = 'short_spy_long_rsp'
            bars_in_position = 0
            
            portfolio['trades'].append(
                f"{date}: ENTER SHORT SPY/LONG RSP | RSI={ratio_rsi:.1f} | Size=${position_size*2:,.0f}"
            )
            
        elif ratio_rsi < RSI_OVERSOLD:
            # Long SPY, Short RSP
            spy_shares = position_size // spy_price
            rsp_shares = -(position_size // rsp_price)
            
            portfolio['spy_shares'] = spy_shares
            portfolio['rsp_shares'] = rsp_shares
            portfolio['cash'] -= (spy_shares * spy_price)
            portfolio['cash'] += (-rsp_shares * rsp_price)
            portfolio['entry_value'] = portfolio_value
            portfolio['entry_bar'] = bar_count
            
            current_position = 'long_spy_short_rsp'
            bars_in_position = 0
            
            portfolio['trades'].append(
                f"{date}: ENTER LONG SPY/SHORT RSP | RSI={ratio_rsi:.1f} | Size=${position_size*2:,.0f}"
            )

# Results
final_value = portfolio['equity'][-1]
total_pnl = final_value - 100000
entry_trades = len([t for t in portfolio['trades'] if 'ENTER' in t])
profit_targets = len([t for t in portfolio['trades'] if 'PROFIT TARGET' in t])
stop_losses = len([t for t in portfolio['trades'] if 'STOP LOSS' in t])
time_exits = len([t for t in portfolio['trades'] if 'TIME LIMIT' in t])
rsi_exits = len([t for t in portfolio['trades'] if 'RSI REVERSION' in t])

print("\n" + "="*60)
print("HYPER-SHORT SCALPING RESULTS")
print("="*60)
print(f"Starting Capital: $100,000")
print(f"Final Portfolio Value: ${final_value:,.2f}")
print(f"Total PnL: ${total_pnl:,.2f}")
print(f"Return: {(total_pnl/100000)*100:.2f}%")
print(f"\nTotal Trades: {entry_trades}")
print(f"  Profit Targets Hit: {profit_targets} ({profit_targets/entry_trades*100:.1f}%)")
print(f"  Stop Losses Hit: {stop_losses} ({stop_losses/entry_trades*100:.1f}%)")
print(f"  Time Limit Exits: {time_exits} ({time_exits/entry_trades*100:.1f}%)")
print(f"  RSI Reversions: {rsi_exits} ({rsi_exits/entry_trades*100:.1f}%)")
print(f"\nStrategy Parameters:")
print(f"  RSI: {RSI_OVERBOUGHT}/{RSI_OVERSOLD}")
print(f"  Max Hold: {MAX_HOLD_BARS} bars (60 min)")
print(f"  Profit Target: {PROFIT_TARGET*100}%")
print(f"  Stop Loss: {STOP_LOSS*100}%")
print("\nLast 30 Trades:")
for trade in portfolio['trades'][-30:]:
    print(f"  {trade}")

# Plot
plt.figure(figsize=(14, 7))
plt.plot(portfolio['dates'], portfolio['equity'], linewidth=1.5)
plt.axhline(y=100000, color='r', linestyle='--', label='Starting Capital')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.title('HYPER-SHORT Scalping Strategy - 60min Max Hold')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

print("\n" + "="*60)
