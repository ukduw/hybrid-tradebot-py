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
    # 1. TWEAK GHOST TICK + PROFIT TAKING PARAMETERS
        # re-entry logic can wait till after PDT...
    # 2. PDT PROBLEMS
        # currently averaging 15-20 tick watchlists - try to reduce to <10-15
        # logic to skip very early premarket gap ups if subsequent tick(s) are down

    # 3. WRITE RE-CONNECT LOGIC IN CASE OF NETWORK FAILURE
        # don't forget the traceback saved in a txt...
        # not just for websocket - write reconnect logic for price streams + logs so they don't fail silently
    # 4. WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority


# PDT PROBLEMS:
# a lot of very-early premarket volatility will barely trigger entry conditions...
    # leads to junk entries - would actually still be profitable in current state if no PDT
    # with PDT, there's no way this will work
    # continue testing with far more stringent watchlist...
# maybe need logic to skip very early premarket gap ups if subsequent tick(s) are downward
    # if first tick > previous close (utils needed...)
    # if x ticks above first tick, another util returns True
    # if util returns true, can enter position
        # other solutions include % above open, red x-min candle (may result in very late entries...)
        # price below vwap, break premarket high... (not preferable)


# unrelated TODO: re-connect logic in case of network failure
    # saved traceback for later...
# unrelated TODO: prevent opening new positions within x time of close


def monitor_trade(setup):
    symbol = setup["symbol"]
    in_position = False
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
                    # stop_price_quote_bar_stream(symbol)
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    # return
                    time.sleep(18000)

            if in_position:
                macd = get_latest_macd(symbol)
                percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100 if macd['MACDs_12_26_9'] != 0 else 0
                macd_perc_high = None

                half_position = round(qty / 2)

                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    return
                
                if 35 < percent_diff < 45: # TWEAK VALUES
                    macd_perc_high = percent_diff
                    while not percent_diff > 44:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100
                        
                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.875: # TWEAK TRAIL
                            if not take_50:
                                take_50 = True
                                qty = qty - half_position
                                close_position(symbol, half_position)
                                print(f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                with open("trade-log/trade_log.txt", "a") as file:
                                    file.write(f"{now}, {symbol}, 50% Exit, {half_position}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                break
                            else:
                                close_position(symbol, qty)
                                print(f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                with open("trade-log/trade_log.txt", "a") as file:
                                    file.write(f"{now}, {symbol}, 2nd 50% Exit, {qty}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                return

                if percent_diff > 44: # TWEAK VALUE
                    macd_perc_high = percent_diff
                    while True:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100

                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.875: # TWEAK TRAIL
                            close_position(symbol, qty)
                            print(f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            with open("trade-log/trade_log.txt", "a") as file:
                                file.write(f"{now}, {symbol}, 100% Exit, {half_position}, {price}" + "\n")
                            pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            return


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

