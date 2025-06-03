import threading
import json
import time
from alpaca_utils import get_current_price, place_order, close_position

import math

# NEEDS EOD "IF IN_POSITION CLOSE_POSITION AT X TIME" (needs datetime?)
# NEEDS LOGIC TO STOP RUNNING AT X TIME (datetime?)
    # SCHEDULED AUTOMATIC RUN... (04:00 - 22:00?)
# NEEDS TRAILING STOP LOSS/TAKE PROFIT LOGIC (i think this needs yfinance data)
# NEEDS TELEGRAM BOT NOTIFICATION INTEGRATION... (holy PITA)
# alpaca api keys, test logic/configs with paper trading

def monitor_trade(config):
    symbol = config.symbol
    entry = config.entry_price
    stop = config.stop_loss
    target = config.take_profit
    qty = math.ceil(config.dollar_value / config.entry_price)
    in_position = False

    while True:
        try:
            price = get_current_price(symbol)

            if not in_position and price >= entry:
                place_order(symbol, qty, "buy")
                print(f"{qty} [{symbol}] bought at {price}")
                in_position = True
            
            elif in_position:
                if price <= stop: 
                    close_position(symbol)
                    print(f"[{symbol}] stop-loss hit. Exiting.")
                    break
                elif price >= target:
                    # NEEDS TRAILING STOP-LOSS LOGIC
                    close_position(symbol)
                    print(f"[{symbol}] take-profit hit. Exiting.")
                    break

            time.sleep(5)

        except Exception as e:
            print(f"[{symbol}] Error: {e}")
            time.sleep(5)

    
with open("configs.json") as f:
    trade_setups = json.load(f)

for setup in trade_setups:
    t = threading.Thread(target=monitor_trade, args=(setup))
    t.start()