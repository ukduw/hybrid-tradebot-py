import threading
import json
import math
import time
import datetime
import pytz
import csv

from alpaca_utils import get_current_price, place_order, close_position, close_all_positions


# TRAILING STOP PLACEHOLDER (1.5%) IN CONFIG CLI DEFAULTS - REMEMBER TO CHANGE IT!
# alpaca api keys, test logic/configs with paper trading
# scheduling: start, stop running at x time

# pushbullet notis

eastern = pytz.timezone("US/Eastern")
exit_open_positions_at = datetime.now(eastern).replace(hour=15, minute=55, second=0, microsecond=0)
now = datetime.now(eastern)

positions_closed = False


def monitor_trade(config):
    symbol = config.symbol
    entry = config.entry_price
    stop = config.stop_loss
    trailing_stop = config.trailing_stop_percentage
    qty = math.ceil(config.dollar_value / config.entry_price)
    day_high = entry
    in_position = False

    print(f"[{symbol}] Monitoring...")

    while True:
        try:
            now = datetime.now(eastern)
            if now >= exit_open_positions_at:
                global positions_closed
                if not positions_closed:
                    close_all_positions()
                    positions_closed = True
                    print("End of day - all positions closed.")
                break

            price = get_current_price(symbol)


            if not in_position and price >= entry:
                place_order(symbol, qty, "buy")
                print(f"{qty} [{symbol}] Market buy placed at {price}")
                in_position = True
                day_high = price
                with open("trade_log", mode="a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(f"{now}, {symbol}, Entry, {qty}, {price}")
            
            elif in_position:
                if price <= stop: 
                    close_position(symbol)
                    print(f"[{symbol}] stop-loss hit. Exiting.")
                    break
                else:
                    if price > day_high:
                        day_high = price
                    if day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                        close_position(symbol)
                        print(f"[{symbol}] take-profit hit. Exiting.")
                        with open("trade_log", mode="a", newline="") as file:
                            writer = csv.writer(file)
                            writer.writerow(f"{now}, {symbol}, Exit, {qty}, {price}")
                        break

            time.sleep(5)

        except Exception as e:
            print(f"[{symbol}] Error: {e}")
            time.sleep(5)

    
with open("configs.json") as f:
    trade_setups = json.load(f)

for setup in trade_setups:
    t = threading.Thread(target=monitor_trade, args=(setup,))
    t.start()