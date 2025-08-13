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

from alpaca_utils import start_price_quote_stream, get_current_price, get_day_high, stop_price_quote_stream, place_order, close_position, close_all_positions, stock_stream

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
threading.Thread(target=start_price_quote_stream, args=(symbols,), daemon=True).start()

shutdown_event = threading.Event()


# PDT PROBLEMS:
    # a lot of very-early premarket volatility will barely trigger entry conditions...
        # leads to junk entries - would actually still be profitable in current state if no PDT
        # with PDT, there's no way this will work
        # continue testing with far more stringent watchlist...
# more testing/time in market to determine best profit-taking parameters...
# for now, implement basic version and incrementally refine it based on time in market

# unrelated TODO: re-connect logic in case of network failure
    # saved traceback for later...



# PRIORITY ORDER:
    # 1. FILTER OUT GHOST TICKS...
        # 
    # 2. WRITE MORE COMPLEX PROFIT-TAKING LOGIC
        # re-entry logic can wait till after PDT...
        # how to deal with junk entries during PDT...?
# ((don't forget to use progressively more stringent watchlists due to PDT...))

    # 3. WRITE RE-CONNECT LOGIC IN CASE OF NETWORK FAILURE
        # don't forget the traceback saved in a txt...
        # not just for websocket - write reconnect logic for price streams + logs so they don't fail silently
    # 4. WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority


# GHOST TICKS
# 1. price-based filtering
    # if price changes by unusual amount, but there is no subsequent confirmation from bid/ask
# 2. volume-based
    # could it be as simple as, if >= 1.00, vol > 100; if between 1.00 and 0.10, vol > 1000; if <0.10, vol > 10000?
# don't think backtesting with historical necessary; could log and visualize data and check against charts?
# would prefer 1; removed other solutions...
# update: seems a lot more complicated than i thought it'd be
    # requires quotes via websocket, they're asynchronous
    # needs sliding quote window to look back at quote history, comparing tick to recent quotes
# can use tick and quote timestamps

# PROFIT TAKING
# options for momentum profit-take: vwap + xSTDEV, vol > 2x avg?, rsi > 75?, long upper wick (5min) indicating exhaustion, rsi bearish divergence...
    # if >=2 conditions true, take partial profit
# NOTE: MACD, RSI seem most straightforward + applicable
    # can combine signals to determine whether 50% or 100% take-profit
    # if macd goes above x%, then pulls back y%, indicates peak - take profit
    # if RSI < 75, take 50% - if RSI > 75, take 100%
    
    # vwap, even with 2x stdev take profit far too soon, and 2x vol not applicable... maybe can use exhaustion wicks
    # i don't think swing low is applicable anymore - doesn't even work on 30min candles; don't want to go as far as 1hr...
        # often takes profit during normal consolidation before another move
    # no longer any need for 15% condition or 15/30min bars, or time-based?
# pandas-ta?
    # fetch recent bars on startup to seed calc (50-100 1min bars)
    # calculate indicators (RSI(14), MACD(12,26,9)) with pandas-ta
    # as new 1min bars come in:
        # append data window
        # recalculate the indicators
        # rewrite main to make take-profit decisions based on these indicators


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
                stop_price_quote_stream(symbol)
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
                    stop_price_quote_stream(symbol)
                    #with open("trade-log/trade_log.txt", "a") as file:
                    #    file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    return
                    #time.sleep(7200)

            if in_position:
                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    return
                else:
                    # if price > day_high:
                        # day_high = price
                    if day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                        close_position(symbol, qty)
                        print(f"[{symbol}] TAKE-PROFT hit. Exiting @ {price}")
                        with open("trade-log/trade_log.txt", "a") as file:
                            file.write(f"{now}, {symbol}, Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting @ {price}")
                        return

            time.sleep(1)

        except Exception as e:
            print(f"[{symbol}] Error: {e}", flush=True)
            # check systemd logs for traceback...
            traceback.print_exc()
            stop_price_quote_stream(symbol)

    

# systemctl stop / ctrl+c cleanup
async def handle_shutdown(signum, frame):
    print("Shutting down...")
    shutdown_event.set()

    try:
        for symbol in symbols:
            stop_price_quote_stream(symbol)
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
        handle_shutdown(None, None)

