#!/usr/bin/env python3
"""
Parameter Optimization for SPY/RSP Pair Strategy
Tests multiple parameter combinations to find best settings
"""

import pandas as pd
import numpy as np
from itertools import product

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def backtest_parameters(spy_df, rsp_df, rsi_high, rsi_low, exit_rsi, capital_usage, stop_loss):
    """Run backtest with given parameters"""
    
    # Calculate ratio and RSI
    df = spy_df.copy()
    df['rsp_close'] = rsp_df['Close']
    df['ratio'] = df['Close'] / df['rsp_close']
    df['ratio_rsi'] = calculate_rsi(df['ratio'], period=14)
    df = df.dropna()
    
    # Initialize
    portfolio = {
        'cash': 100000,
        'spy_shares': 0,
        'rsp_shares': 0,
        'equity': 100000,
        'entry_value': 0
    }
    
    current_position = None
    trades = 0
    
    for idx, row in df.iterrows():
        spy_price = row['Close']
        rsp_price = row['rsp_close']
        ratio_rsi = row['ratio_rsi']
        
        # Calculate portfolio value
        portfolio_value = portfolio['cash'] + \
                          portfolio['spy_shares'] * spy_price + \
                          portfolio['rsp_shares'] * rsp_price
        portfolio['equity'] = portfolio_value
        
        # Check stop loss
        if current_position is not None and portfolio['entry_value'] > 0:
            pnl_pct = (portfolio_value - portfolio['entry_value']) / portfolio['entry_value']
            if pnl_pct <= -stop_loss:
                # Stop loss hit - close position
                portfolio['cash'] += portfolio['spy_shares'] * spy_price
                portfolio['cash'] += portfolio['rsp_shares'] * rsp_price
                portfolio['spy_shares'] = 0
                portfolio['rsp_shares'] = 0
                current_position = None
                portfolio['entry_value'] = 0
                continue
        
        # Exit logic
        if current_position is not None:
            should_exit = False
            
            if current_position == 'short_spy_long_rsp' and ratio_rsi < exit_rsi:
                should_exit = True
            elif current_position == 'long_spy_short_rsp' and ratio_rsi > (100 - exit_rsi):
                should_exit = True
            
            if should_exit:
                portfolio['cash'] += portfolio['spy_shares'] * spy_price
                portfolio['cash'] += portfolio['rsp_shares'] * rsp_price
                portfolio['spy_shares'] = 0
                portfolio['rsp_shares'] = 0
                current_position = None
                portfolio['entry_value'] = 0
        
        # Entry logic
        if current_position is None:
            position_size = portfolio_value * capital_usage / 2
            
            if ratio_rsi > rsi_high:
                # Short SPY, Long RSP
                spy_shares = -(position_size // spy_price)
                rsp_shares = position_size // rsp_price
                
                portfolio['spy_shares'] = spy_shares
                portfolio['rsp_shares'] = rsp_shares
                portfolio['cash'] -= (rsp_shares * rsp_price)
                portfolio['cash'] += (-spy_shares * spy_price)
                portfolio['entry_value'] = portfolio_value
                current_position = 'short_spy_long_rsp'
                trades += 1
                
            elif ratio_rsi < rsi_low:
                # Long SPY, Short RSP
                spy_shares = position_size // spy_price
                rsp_shares = -(position_size // rsp_price)
                
                portfolio['spy_shares'] = spy_shares
                portfolio['rsp_shares'] = rsp_shares
                portfolio['cash'] -= (spy_shares * spy_price)
                portfolio['cash'] += (-rsp_shares * rsp_price)
                portfolio['entry_value'] = portfolio_value
                current_position = 'long_spy_short_rsp'
                trades += 1
    
    # Final results
    final_value = portfolio['equity']
    total_return = (final_value - 100000) / 100000
    
    return {
        'final_value': final_value,
        'return_pct': total_return * 100,
        'trades': trades
    }

# Load data
print("Loading SPY and RSP 1-hour data...")
spy_df = pd.read_csv('data/SPY_1Hour_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)
rsp_df = pd.read_csv('data/RSP_1Hour_stock_alpaca_clean.csv', index_col='Datetime', parse_dates=True)

# Align
common_dates = spy_df.index.intersection(rsp_df.index)
spy_df = spy_df.loc[common_dates]
rsp_df = rsp_df.loc[common_dates]

print(f"Testing on {len(spy_df)} bars (2024-2025)")
print("\nOptimizing parameters...")
print("="*80)

# Parameter ranges to test
rsi_highs = [65, 70, 75, 80]           # Overbought thresholds
rsi_lows = [20, 25, 30, 35]            # Oversold thresholds
exit_rsis = [45, 50, 55]                # Exit at this RSI level
capital_usages = [0.50, 0.70, 0.90]    # % of capital per trade
stop_losses = [0.01, 0.02, 0.03]       # Stop loss %

# Store results
results = []

total_combinations = len(list(product(rsi_highs, rsi_lows, exit_rsis, capital_usages, stop_losses)))
print(f"Testing {total_combinations} parameter combinations...\n")

count = 0
for rsi_high, rsi_low, exit_rsi, capital_usage, stop_loss in product(rsi_highs, rsi_lows, exit_rsis, capital_usages, stop_losses):
    count += 1
    
    result = backtest_parameters(spy_df, rsp_df, rsi_high, rsi_low, exit_rsi, capital_usage, stop_loss)
    
    results.append({
        'rsi_high': rsi_high,
        'rsi_low': rsi_low,
        'exit_rsi': exit_rsi,
        'capital_usage': capital_usage,
        'stop_loss': stop_loss,
        'return': result['return_pct'],
        'trades': result['trades'],
        'final_value': result['final_value']
    })
    
    if count % 50 == 0:
        print(f"Progress: {count}/{total_combinations} tested...")

# Convert to DataFrame and sort by return
results_df = pd.DataFrame(results)
results_df = results_df.sort_values('return', ascending=False)

print("\n" + "="*80)
print("TOP 10 PARAMETER COMBINATIONS")
print("="*80)
print(results_df.head(10).to_string(index=False))

print("\n" + "="*80)
print("BOTTOM 10 PARAMETER COMBINATIONS")
print("="*80)
print(results_df.tail(10).to_string(index=False))

# Save results
results_df.to_csv('optimization_results.csv', index=False)
print(f"\n✅ Full results saved to: optimization_results.csv")

# Best parameters
best = results_df.iloc[0]
print("\n" + "="*80)
print("BEST PARAMETERS FOUND:")
print("="*80)
print(f"RSI Overbought: {best['rsi_high']}")
print(f"RSI Oversold: {best['rsi_low']}")
print(f"Exit RSI: {best['exit_rsi']}")
print(f"Capital Usage: {best['capital_usage']*100}%")
print(f"Stop Loss: {best['stop_loss']*100}%")
print(f"Return: {best['return']:.2f}%")
print(f"Trades: {int(best['trades'])}")
print(f"Final Value: ${best['final_value']:,.2f}")
print("="*80)
