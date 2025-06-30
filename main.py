import threading
import json
import math
import time
import datetime
import pytz

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


day_trade_counter = 0
day_trade_lock = threading.Lock()

def can_enter_trade():
    global day_trade_counter
    with day_trade_lock:
        if day_trade_counter < 1:
            day_trade_counter += 1
            return True
        else: 
            return False


CONFIG_PATH = "configs.json"
last_config_mtime = None
with open("configs.json", "r") as f:
    cached_configs = json.load(f)

def load_configs_on_modification():
    global last_config_mtime, cached_configs
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime != last_config_mtime:
            last_config_mtime = mtime
            with open(CONFIG_PATH, "r") as f:
                cached_configs = json.load(f)
            print("[MOD] Configs updated")
    except Exception as e:
        print(f"[LOOP] Configs mid-modification: {e}")
    return cached_configs


symbols = [setup["symbol"] for setup in cached_configs]
threading.Thread(target=start_price_stream, args=(symbols,), daemon=True).start()

# profit-taking logic
    # if before x time (e.g. 6AM, US/Eastern (EDT)), normal trail logic
    # elif +15% from entry, ~1hr timeout(?), swing low exit
        # any need for partial take-profit...?
# again, needs to be easy to revert when market is slow...
# needs additional logic for if timeout overlaps with close_all_positions() time

# 1s bar data is far too granular for ~1hr strategies...
# i think i need to stream, e.g., 5min bars for broader trends, 1s for entry/exit
    # need to combine both for exit logic?
    # actually, which is more efficient: 1) streaming 1s AND 5min, 2) calculating 5min FROM 1s...?

# ...pandas?
# look into AWS - this laptop too sus for all these threads...


def monitor_trade(setup):
    symbol = setup["symbol"]
    in_position = False

    print(f"[{symbol}] Monitoring...")

    while True:
        configs = load_configs_on_modification()
        updated_setup = next((s for s in configs if s["symbol"] == symbol), None)

        if not updated_setup:
            print(f"[{symbol}] Removed from configs. Stopping thread.")
            return
        
        #if updated_setup != setup:
            #in_position = False
            #setup = updated_setup

        entry = updated_setup["entry_price"]
        stop = updated_setup["stop_loss"]
        trailing_stop = updated_setup["trailing_stop_percentage"]
        qty = math.ceil(updated_setup["dollar_value"] / updated_setup["entry_price"])
        day_high = entry

        price = get_current_price(symbol)
        if price is None:
            time.sleep(2)
            continue

        try:
            now = datetime.datetime.now(eastern)
            if now >= exit_open_positions_at:
                global positions_closed
                if not positions_closed:
                    close_all_positions()
                    positions_closed = True
                    print("End of day - all positions closed.")
                return

            if not in_position and can_enter_trade() and price >= entry:
                #place_order(symbol, qty)
                print(f"{qty} [{symbol}] Market buy placed at {price}")
                in_position = True
                day_high = price
                with open("trade-log/trade_log.txt", "a") as file:
                    file.write(f"{now},{symbol},Entry,{qty},{price}" + "\n")
                pb.push_note("Hybrid bot", f"{qty} [{symbol}] Market buy placed at {price}")
            elif not in_position and price >= entry:
                print(f"Skipped [{symbol}] @ {price}, PDT limit hit...")
                return

            elif in_position:
                if price < stop: 
                    close_position(symbol)
                    print(f"[{symbol}] stop-loss hit. Exiting.")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},Exit,{qty},{price}" + "\n")
                    pb.push_note(f"[{symbol}] stop-loss hit. Exiting.")
                    return
                else:
                    if price > day_high:
                        day_high = price
                    if day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                        close_position(symbol)
                        print(f"[{symbol}] take-profit hit. Exiting.")
                        with open("trade-log/trade_log.txt", "a") as file:
                            file.write(f"{now}, {symbol}, Exit, {qty}, {price}" + "\n")
                        pb.push_note(f"[{symbol}] take-profit hit. Exiting.")
                        return

            time.sleep(1)

        except Exception as e:
            print(f"[{symbol}] Error: {e}")
            time.sleep(1)

    
for setup in cached_configs:
    t = threading.Thread(target=monitor_trade, args=(setup,))
    t.start()