#!/usr/bin/env python3
"""
LIVE Paper Trading - SPY/RSP Pair Strategy
Runs continuously, checking signals every 5 minutes
"""

import time
import pandas as pd
from datetime import datetime, timezone
from pipeline.alpaca import get_rest

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Strategy parameters
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
CAPITAL_USAGE = 0.90
LOOKBACK_BARS = 100  # How many 5-min bars to fetch for RSI calculation

print("="*60)
print("LIVE SPY/RSP PAIR TRADING STRATEGY")
print("="*60)
print(f"RSI Thresholds: Overbought={RSI_OVERBOUGHT}, Oversold={RSI_OVERSOLD}")
print(f"Capital Usage: {CAPITAL_USAGE*100}%")
print("Checking signals every 5 minutes...")
print("="*60)

# Connect to Alpaca
api = get_rest()

# State tracking
current_position = None  # None, 'short_spy_long_rsp', or 'long_spy_short_rsp'

def get_account_value():
    """Get current portfolio value"""
    account = api.get_account()
    return float(account.portfolio_value)

def get_current_price(symbol):
    """Get latest price for a symbol"""
    bars = api.get_bars(symbol, '1Min', limit=1).df
    if not bars.empty:
        return bars['close'].iloc[-1]
    return None

def get_ratio_rsi():
    """Calculate current SPY/RSP ratio RSI"""
    # Fetch recent 5-min bars
    spy_bars = api.get_bars('SPY', '5Min', limit=LOOKBACK_BARS).df
    rsp_bars = api.get_bars('RSP', '5Min', limit=LOOKBACK_BARS).df
    
    # Align timestamps
    common_idx = spy_bars.index.intersection(rsp_bars.index)
    spy_bars = spy_bars.loc[common_idx]
    rsp_bars = rsp_bars.loc[common_idx]
    
    # Calculate ratio
    ratio = spy_bars['close'] / rsp_bars['close']
    
    # Calculate RSI
    rsi = calculate_rsi(ratio, period=14)
    
    return rsi.iloc[-1] if not rsi.empty else None

def close_all_positions():
    """Close any open SPY/RSP positions"""
    global current_position
    
    try:
        api.close_all_positions()
        print(f"[{datetime.now(timezone.utc)}] Closed all positions")
        current_position = None
    except Exception as e:
        print(f"Error closing positions: {e}")

def enter_trade(position_type, ratio_rsi):
    """Enter a pair trade"""
    global current_position
    
    try:
        account_value = get_account_value()
        position_size = account_value * CAPITAL_USAGE / 2
        
        spy_price = get_current_price('SPY')
        rsp_price = get_current_price('RSP')
        
        if not spy_price or not rsp_price:
            print("Could not get current prices")
            return
        
        spy_qty = int(position_size / spy_price)
        rsp_qty = int(position_size / rsp_price)
        
        if position_type == 'short_spy_long_rsp':
            # Short SPY, Long RSP
            api.submit_order(symbol='SPY', qty=spy_qty, side='sell', type='market', time_in_force='day')
            api.submit_order(symbol='RSP', qty=rsp_qty, side='buy', type='market', time_in_force='day')
            
            print(f"\n[{datetime.now(timezone.utc)}] ENTERED TRADE")
            print(f"  Position: SHORT SPY, LONG RSP")
            print(f"  SPY: Sold {spy_qty} shares @ ${spy_price:.2f}")
            print(f"  RSP: Bought {rsp_qty} shares @ ${rsp_price:.2f}")
            print(f"  Ratio RSI: {ratio_rsi:.1f}")
            print(f"  Total Size: ${position_size*2:,.0f}\n")
            
        elif position_type == 'long_spy_short_rsp':
            # Long SPY, Short RSP
            api.submit_order(symbol='SPY', qty=spy_qty, side='buy', type='market', time_in_force='day')
            api.submit_order(symbol='RSP', qty=rsp_qty, side='sell', type='market', time_in_force='day')
            
            print(f"\n[{datetime.now(timezone.utc)}] ENTERED TRADE")
            print(f"  Position: LONG SPY, SHORT RSP")
            print(f"  SPY: Bought {spy_qty} shares @ ${spy_price:.2f}")
            print(f"  RSP: Sold {rsp_qty} shares @ ${rsp_price:.2f}")
            print(f"  Ratio RSI: {ratio_rsi:.1f}")
            print(f"  Total Size: ${position_size*2:,.0f}\n")
        
        current_position = position_type
        
    except Exception as e:
        print(f"Error entering trade: {e}")

# Main trading loop
print("\nStarting live trading loop...\n")

try:
    while True:
        now = datetime.now(timezone.utc)
        
        # Get ratio RSI
        ratio_rsi = get_ratio_rsi()
        
        if ratio_rsi is None:
            print(f"[{now}] Could not calculate ratio RSI, skipping...")
            time.sleep(300)  # Wait 5 minutes
            continue
        
        print(f"[{now}] Ratio RSI: {ratio_rsi:.2f} | Position: {current_position or 'None'}")
        
        # Trading logic
        if current_position is None:
            # Look for entry signals
            if ratio_rsi > RSI_OVERBOUGHT:
                enter_trade('short_spy_long_rsp', ratio_rsi)
            elif ratio_rsi < RSI_OVERSOLD:
                enter_trade('long_spy_short_rsp', ratio_rsi)
        
        else:
            # Look for exit signals
            should_exit = False
            
            if current_position == 'short_spy_long_rsp' and ratio_rsi < 50:
                should_exit = True
            elif current_position == 'long_spy_short_rsp' and ratio_rsi > 50:
                should_exit = True
            
            if should_exit:
                account_value = get_account_value()
                print(f"\n[{now}] EXITING TRADE")
                print(f"  Ratio RSI: {ratio_rsi:.1f}")
                print(f"  Account Value: ${account_value:,.2f}\n")
                close_all_positions()
        
        # Wait 5 minutes before next check
        time.sleep(300)

except KeyboardInterrupt:
    print("\n\nStopping live trading...")
    print("Closing any open positions...")
    close_all_positions()
    print("Done!")

