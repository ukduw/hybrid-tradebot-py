import threading
import json
import math
import time
import datetime
import pytz
import csv

from pushbullet import Pushbullet
from dotenv import load_dotenv
import os

load_dotenv()
PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")
pb = Pushbullet(PB_API_KEY)

from alpaca_utils import start_price_stream, get_current_price, place_order, close_position, close_all_positions

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=15, minute=55, second=0, microsecond=0)

positions_closed = False


with open("configs.json") as f:
    trade_setups = json.load(f)

symbols = [setup["symbol"] for setup in trade_setups]
threading.Thread(target=start_price_stream, args=(symbols,), daemon=True).start()


def monitor_trade(setup):
    symbol = setup["symbol"]
    entry = setup["entry_price"]
    stop = setup["stop_loss"]
    trailing_stop = setup["trailing_stop_percentage"]
    qty = math.ceil(setup["dollar_value"] / setup["entry_price"])
    day_high = entry
    in_position = False

    print(f"[{symbol}] Monitoring...")

    while True:
        price = get_current_price(symbol)
        if price is None:
            continue

        try:
            now = datetime.datetime.now(eastern)
            if now >= exit_open_positions_at:
                global positions_closed
                if not positions_closed:
                    close_all_positions()
                    positions_closed = True
                    print("End of day - all positions closed.")
                break

            if not in_position and price >= entry:
                place_order(symbol, qty, "buy")
                print(f"{qty} [{symbol}] Market buy placed at {price}")
                in_position = True
                day_high = price
                with open("trade_log", mode="a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(f"{now}, {symbol}, Entry, {qty}, {price}")
                pb.push_note("Hybrid bot", f"{qty} [{symbol}] Market buy placed at {price}")
            
            elif in_position:
                if price <= stop: 
                    close_position(symbol)
                    print(f"[{symbol}] stop-loss hit. Exiting.")
                    with open("trade_log", mode="a", newline="") as file:
                        writer = csv.writer(file)
                        writer.writerow(f"{now}, {symbol}, Exit, {qty}, {price}")
                    pb.push_note(f"[{symbol}] stop-loss hit. Exiting.")
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
                        pb.push_note(f"[{symbol}] take-profit hit. Exiting.")
                        break

            time.sleep(1)

        except Exception as e:
            print(f"[{symbol}] Error: {e}")
            time.sleep(1)

    
for setup in trade_setups:
    t = threading.Thread(target=monitor_trade, args=(setup,))
    t.start()