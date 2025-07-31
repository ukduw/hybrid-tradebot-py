import threading
import json
import time
import datetime
import pytz
import traceback
import asyncio
import signal
import sys

from pushbullet import Pushbullet
from dotenv import load_dotenv
import os

load_dotenv()
PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")
pb = Pushbullet(PB_API_KEY)

from alpaca_utils import start_price_stream, get_current_price, get_day_high, stop_price_stream, place_order, close_position, close_all_positions, stock_stream

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=15, minute=55, second=0, microsecond=0)


day_trade_counter = 0
day_trade_lock = threading.Lock()


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

shutdown_event = threading.Event()

# profit-taking logic
    # if before x time (e.g. 6AM, US/Eastern (EDT)), momentum logic
    # elif +15% from entry(?), swing low exit
        # any need for partial take-profit...?
# combination logic: momentum AND swing low for all, regardless of time?
# re-entry logic?

# ...pandas?
# more testing/time in market to determine best profit-taking parameters...
# write event-driven version in meantime...


# testing notes:
    # 1. more complex profit-taking NEEDED - even BIG wins entered at perfect time are not captured with current method; early volatility reaches take-profit condition far too soon...
        # forget 1hr timeout method... use 5min or 10min candles for swing low instead?
        # is the 15% condition still needed?
        # maybe early (time-based) momentum take-profit? in addition to swing low after x time
        # re-entry logic?
    # 2. a lot of very-early premarket volatility will barely trigger entry conditions...
        # leads to junk entries - would actually still be profitable in current state if no PDT
        # with PDT, there's no way this will work
        # continue testing with far more stringent watchlist...


# entry/exit problem:
    # some entries (and now exits) are triggered without conditions being met...
    # have tested the websocket/price stream, which doesn't seem to be the problem
    # also doesn't seem to be a problem with bot logic
# potential causes troubleshooting:
    # 1. use asyncio event to wait for first trade event before conditions are assessed
    # 2. add systemd cleanup (ExecStopPost)
    # 3. json load issues?
    # i don't think it has to do with entry/exit parameter misload or overwriting... leave for now

# will change price stream to log each tick and manually cross-reference with entries...
    # e.g. catch ghost/malformed trades - if this is the case, possible solution is waiting for n ticks above threshold 
    # e.g. momentary <1s spikes/drops that do not show via candlesticks (shouldn't there be a wick anyways...?) - if so... smoothing threshold??

# unrelated TODO: re-connect logic in case of network failure
    # saved traceback for later...


def monitor_trade(setup):
    symbol = setup["symbol"]
    in_position = False

    print(f"[{symbol}] Monitoring... {setup["entry_price"]}, {setup["stop_loss"]}")

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
        qty = round(updated_setup["dollar_value"] / updated_setup["entry_price"])
        # day_high = entry

        price = get_current_price(symbol)
        if price is None:
            time.sleep(2)
            continue
        day_high = get_day_high(symbol)
        if day_high is None:
            time.sleep(2)
            continue

        try:
            now = datetime.datetime.now(eastern)
            if now >= exit_open_positions_at:
                close_all_positions()
                print("End of day - all positions closed.")
                stop_price_stream(symbol)
                return

            if not in_position:
                global day_trade_counter
                if day_trade_counter < 1 and price > entry:
                    with day_trade_lock:
                        if day_trade_counter < 1:
                            place_order(symbol, qty)
                            print(f"{qty} [{symbol}] BUY @ {price}")
                            in_position = True
                            day_high = price
                            day_trade_counter += 1
                            with open("trade-log/trade_log.txt", "a") as file:
                                file.write(f"{now},{symbol},ENTRY,{qty},{price}" + "\n")
                            pb.push_note("Hybrid bot", f"{qty} [{symbol}] BUY @ {price}")
                elif not day_trade_counter < 1 and price > entry:
                    print(f"Skipped [{symbol}] @ {price}, PDT limit hit...")
                    stop_price_stream(symbol)
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    return

            if in_position:
                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] stop-loss hit. Exiting.")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] stop-loss hit. Exiting.")
                    return
                else:
                    # if price > day_high:
                        # day_high = price
                    if day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                        close_position(symbol, qty)
                        print(f"[{symbol}] take-profit hit. Exiting.")
                        with open("trade-log/trade_log.txt", "a") as file:
                            file.write(f"{now}, {symbol}, Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] take-profit hit. Exiting.")
                        return

            time.sleep(1)

        except Exception as e:
            print(f"[{symbol}] Error: {e}", flush=True)
            # check systemd logs for traceback...
            traceback.print_exc()
            stop_price_stream(symbol)

    

# systemctl stop / ctrl+c cleanup
def handle_shutdown(signum, frame):
    print("Shutting down...")
    shutdown_event.set()

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(stock_stream.unsubscribe_all())
        loop.run_until_complete(stock_stream.stop_ws())
    except Exception as e:
        print(f"[Shutdown] Error during cleanup: {e}")
    finally:
        print("Cleanup complete. Exiting...")
        sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)



if __name__ == "__main__":
    for setup in cached_configs:
        t = threading.Thread(target=monitor_trade, args=(setup,))
        t.start()

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(1)
    except KeyboardInterrupt:
        handle_shutdown(None, None)

