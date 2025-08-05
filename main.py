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


# entry/exit problem (UPDATE: CAUSE IDENTIFIED):
    # ghost ticks in raw trade prints vs aggregated/charted data
        # most charting eliminates:
            # 1. odd-lot trades (<100 shares)
            # 2. out-of-band trades (delayed, corrected, invalid... trades)
            # 3. off-exchange trades (dark pool, test prints, tape corrections...)
            # 4. "conditioned" trades (auction prints, opening/closing cross, vwap-only trades...)
        # MOST DO NOT CHART PREMARKET CANDLES UNLESS SUFFICIENT VOLUME
        # LOW-VOLUME TICKS TRIGGER CONDITION(S) FOR ENTRY
    # potential fixes:
        # 1. filter trades by volume or conditions (need to test for available conditions)
            # run tick logs, size/condition prints & bot - use actual cases to determine conditions
        # 2. time-weighted/confirmation logic
            # e.g. n ticks in a row meet condition OR ticks above threshold for > 2s

# PROFIT-TAKING & PDT PROBLEMS:
    # 1. MORE COMPLEX PROFIT-TAKING NEEDED - even BIG wins entered at perfect time are not captured with current method; early volatility reaches take-profit condition far too soon...
        # forget 1hr timeout method... use 15min or 30min candles for swing low/combination logic instead?
            # are 30min candles needed...? 15min seems fine even for longer trades
            # ideal: 30min to 2hr, average 1hr...
            # but <30min plays will be missed without momentum logic...
        # maybe early (time-based?) momentum take-profit? in addition to swing low after x time(?)
            # this is NEEDED - a swing low requires AT LEAST 3, 4 bars (at least 45-60min)
                # wait... if exit logic uses tick data, then it'd be minimum 2 bars?
                # even so, for short-term spikes, the second bar would already be too late... and keep in mind decision making would occur during the 3rd bar
        # while number of bars < 4, use momentum take-profit on the way UP?
        # if bars >= 4, use swing low?
            # start storing bar counter after entry?
            # in that case, i think i need to keep the if >=15% condition
            # e.g. entry triggered, but continues to fluctuate in range ABOVE stop-loss
            # this could trigger swing low "profit-take" before anything even happens; 15% confirms it's a runner
        # swing low self-explanatory
        # momentum/volatility options: RSI, MACD, ATR, Bollinger...
    # 2. a lot of very-early premarket volatility will barely trigger entry conditions...
        # leads to junk entries - would actually still be profitable in current state if no PDT
        # with PDT, there's no way this will work
        # continue testing with far more stringent watchlist...
# more testing/time in market to determine best profit-taking parameters...
# for now, implement basic version and incrementally refine it based on time in market

# unrelated TODO: re-connect logic in case of network failure
    # saved traceback for later...



# PRIORITY ORDER:
    # 1. LOG THE 1) TICK DATA, 2) TRADE.SIZE, TRADE.CONDITIONS, 3) BOT ENTRIES/EXITS
        # TODO: use results to determine conditions ticks must pass to be able to trigger entry/exit
        # TODO: write solution(s) above (lines 77-82)
    # 2. WRITE MORE COMPLEX 15/30MIN BAR PROFIT-TAKING LOGIC
        # 15% condition needed, 15min bars, per thread bar counter after entry
        # below x bars (short spike), momentum take-profit (how can this not trigger prematurely if it's a longer-term play...?)
            # need to research/test RSI, MACD, ATR, Bollinger more before decision...
        # above x bars (longer-term spiking/trend), swing low take-profit
            # every long spike has to safely fail the short spike conditions
            # yet the short spike conditions have to be sensitive enough to take profit without waiting too long...
            # maybe volume based??? this would require a lot of testing...
        # DOES need re-entry logic
        # and probably partial take-profits on the way up...
# ((don't forget to use progressively more stringent watchlists due to PDT...))
    # 3. WRITE RE-CONNECT LOGIC IN CASE OF NETWORK FAILURE
        # don't forget the traceback saved in a txt...
        # not just for websocket - write reconnect logic for price streams + logs so they don't fail silently
    # 4. WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority


# note: after some research, the 'I' character in trade metadata (trade.conditions) means ODD LOT TRADE (<100 shares volume)
    # depending on the stock, the proportion of trades with 'I' code can be very different...
    # may not be the best solution - maybe in handler/utils, keep dictionary + boolean to determine if, if multiple ticks are above/below condition, trade-able...
    # just found an exhaust of "ghost ticks" that have high volume AND multi-tick... so neither solution would work
# update: i misunderstood - i don't think price streams are silently failing, but there also isn't reconnect logic so i'll add that to the end of the TODO list
# PRIORITY: write basic handler improvements for ghost ticks
    # then can finally move on to profit-taking logic (momentum + swing low, partial profits + re-entry logic)...


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
            stop_price_stream(symbol)

    

# systemctl stop / ctrl+c cleanup
def handle_shutdown(signum, frame):
    print("Shutting down...")
    shutdown_event.set()

    try:
        for symbol in symbols:
            stop_price_stream(symbol)
        stock_stream.stop_ws()

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

