import threading
import json
import time
import datetime
import pytz
import traceback
import signal
import sys

from pushbullet import Pushbullet
from dotenv import load_dotenv
import os

load_dotenv()
PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")
pb = Pushbullet(PB_API_KEY)

from alpaca_utils import start_price_quote_bar_stream, get_current_price, get_day_high, get_latest_macd, stop_price_quote_bar_stream, place_order, close_position, close_all_positions, stock_stream

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
threading.Thread(target=start_price_quote_bar_stream, args=(symbols,), daemon=True).start()

shutdown_event = threading.Event()


# PRIORITY ORDER:
    # 1. FILTER OUT GHOST TICKS...
    # 2. WRITE MORE COMPLEX PROFIT-TAKING LOGIC
        # re-entry logic can wait till after PDT...
    # 3. PDT PROBLEMS
        # currently averaging 15-20 tick watchlists - try to reduce to <10-15
        # logic to skip very early premarket gap ups if subsequent tick(s) are down

    # 4. WRITE RE-CONNECT LOGIC IN CASE OF NETWORK FAILURE
        # don't forget the traceback saved in a txt...
        # not just for websocket - write reconnect logic for price streams + logs so they don't fail silently
    # 5. WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority


# GHOST TICKS
# implemented tick filter based on quotes
# need to test and tweak to prevent filtering valid ticks

# PROFIT TAKING
# implemented bars/macd calc...
# rewrite main to make take-profit decisions based on indicator
    # e.g. variable(s) to store boolean
    # get_latest_macd returns dataframe; extract data, calc ratio, etc...
    # variable(s) switch to True if ratio >45%, then loops, monitoring fall back below threshold - SELL
    # different conditions determine which variable switches to True - determines 50% or 100% take profit
# more testing/time in market to determine best profit-taking parameters...
# for now, implement basic version and incrementally refine it based on time in market

# PDT PROBLEMS:
# a lot of very-early premarket volatility will barely trigger entry conditions...
    # leads to junk entries - would actually still be profitable in current state if no PDT
    # with PDT, there's no way this will work
    # continue testing with far more stringent watchlist...
# maybe need logic to skip very early premarket gap ups if subsequent tick(s) are downward


# unrelated TODO: re-connect logic in case of network failure
    # saved traceback for later...
# unrelated TODO: prevent opening new positions within x time of close


def monitor_trade(setup):
    symbol = setup["symbol"]
    in_position = False
    take_100 = False
    take_50 = False

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
                stop_price_quote_bar_stream(symbol)
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
                    stop_price_quote_bar_stream(symbol)
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    # return
                    time.sleep(18000)

            if in_position:
                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    return
                elif day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                    close_position(symbol, qty)
                    print(f"[{symbol}] TAKE-PROFT hit. Exiting @ {price}")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now}, {symbol}, Exit, {qty}, {price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting @ {price}")
                    return
                
                # macd = get_latest_macd()
                    # note: macd line = 26 - 12 EMA, signal line = 9-period EMA of the macd line, histogram = difference between the 2
                    # could just use histogram...
                    # but would that be relative to each stock? if so, calc ratio between the two rather than difference?
                    # after looking at 1min macd, consider refactoring to 5-15min?
                        # keep in mind that decisions will only be made AFTER complete candles come in...
                # if 0.50 > macd_ratio > 0.40:
                    # take_50 = True
                # if macd_ratio > 0.50:
                    # take_50 = False
                    # take_100 = True
                # need variables to track whether ratio has fallen below again?

                # macd_line / signal_line... ratio - fine, but need to account for sign and division by 0, and becomes unstable near 0
                # (macd_line - signal_line) / signal_line) * 100... if signal_line != 0
                    # percentage difference - more straightforward
                # (macd_line - signal_line) / price
                    # normalized by price - would probably require a lot of testing...
                    # right now, leaning towards 2nd solution

            time.sleep(1)

        except Exception as e:
            print(f"[{symbol}] Error: {e}", flush=True)
            # check systemd logs for traceback...
            traceback.print_exc()
            stop_price_quote_bar_stream(symbol)

    

# systemctl stop / ctrl+c cleanup
async def handle_shutdown(signum, frame):
    print("Shutting down...")
    shutdown_event.set()

    try:
        for symbol in symbols:
            stop_price_quote_bar_stream(symbol)
        await stock_stream.stop_ws()

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
        handle_shutdown(None, None) # needs to be awaited??

