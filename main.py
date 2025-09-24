import asyncio
import json
import time
import datetime
import pytz
import traceback
import signal
import aiofiles
import requests

from pushbullet import Pushbullet
from dotenv import load_dotenv
import os

load_dotenv()

PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")

class DummyPB:
    def push_note(self, title, body):
        print(f"(PB Failed) Unsent notification: {title}, {body}")

pb = DummyPB()

pb_reconnect_tries = 0
while pb_reconnect_tries < 5: # low due to risk of getting stuck in loop past premarket open...
    try:
        pb = Pushbullet(PB_API_KEY)
        break
    except requests.exceptions.ConnectionError as e:
        pb_reconnect_tries += 1
        print(f"PB connection failed({pb_reconnect_tries}/5), retrying in 10s...", e)
        time.sleep(10)


from alpaca_utils import start_price_quote_bar_stream, get_current_price, get_day_high, get_bar_data, stop_price_quote_bar_stream, place_order, close_position, close_all_positions, stock_stream
    # NOTE: get_day_high, get_latest_macd, get_latest_rsi, close_all_positions - consider removing, deleting utils

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=17, minute=55, second=0, microsecond=0)


day_trade_counter = 0
day_trade_lock = asyncio.Lock()


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


# PRIORITY ORDER:
    # 1. MONITOR & TWEAK: 1) GHOST TICK, 2) PROFIT TAKING, 3) GAP-UP-FAKEOUT PROTECTION PARAMETERS
        # run and test...
        # re-entry logic can wait till after PDT... (is it needed at all?)
        # try to reduce 15-20 ticker watchlist to <10-15 (averages 30-40 when market hot...)

    # WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority
        # event = asyncio.Event(), then price stream handler calls event.set() when data arrives...

# ghost tick and gap up protections seem to work really well; continue monitoring for a while longer...
    # e.g. successfully stopped 1) different types of entry-trigger-stop-trigger patterns, 2) gap up, sell off, 3) gap up, momentary spike, stop-loss
    # potential problems: sometimes unintendedly considered gap up (e.g. ticks under entry are all odd lots; first non-odd lot is above entry)
        # i've also seen odd lots form significant price action, yet an entry isn't triggered until non-odd lot comes through...
        # remember 1.5% gap up condition can be changed

# urgent:
# 2. take-profit conditions still insufficient for very slow and very fast spikes
    # current vwap strategies seem inadequate to capture wide range of different wins...
    # re-think, for example, forget stdev bands and use % above vwap?
        # unsure whether 1m data would lead to more timely exits or early exits... needs testing
# 5. rewrite README


async def monitor_trade(setup):
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
        qty = round(updated_setup["dollar_value"] / updated_setup["entry_price"])

        price = get_current_price(symbol)
        if price is None:
            await asyncio.sleep(2)
            continue
        # day_high = get_day_high(symbol)
        # if day_high is None:
        #     await asyncio.sleep(2)
        #     continue

        try:
            now = datetime.datetime.now(eastern)
            if now >= exit_open_positions_at:
                if in_position:
                    if take_50:
                        close_position(symbol, other_half)
                        print(f"[{symbol}] EOD, 2nd 50% Exit @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, EOD 2nd 50% Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] EOD, 2nd Exiting 50% position @ {price}")
                    else:
                        close_position(symbol, qty)
                        print(f"[{symbol}] EOD, 100% Exit @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, EOD 100% Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] EOD, Exiting 100% position @ {price}")

                await stop_price_quote_bar_stream(symbol)
                return


            if not in_position:
                global day_trade_counter
                if day_trade_counter < 1 and price > entry:
                    async with day_trade_lock:
                        if day_trade_counter < 1:
                            now = datetime.datetime.now(eastern).time()
                            if now < datetime.time(17,30): # ~30min before end, tweak
                                # place_order(symbol, qty)
                                print(f"{qty} [{symbol}] BUY @ {price}")
                                in_position = True
                                day_trade_counter += 1
                                async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                    await file.write(f"{now},{symbol},ENTRY,{qty},{price}" + "\n")
                                pb.push_note("Hybrid bot", f"{qty} [{symbol}] BUY @ {price}")
                elif not day_trade_counter < 1 and price > entry:
                    print(f"Skipped [{symbol}] @ {price}, PDT limit hit...")
                    # await stop_price_quote_bar_stream(symbol)
                    async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                        await file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    # return
                    await asyncio.sleep(18000)

                await asyncio.sleep(1)

            if in_position:
                half_position = round(qty / 2)
                other_half = qty - half_position
                vwap, stdev, close_5m, high_5m, timestamp_5m = get_bar_data(symbol)

                if price < stop:
                    if take_50:
                        close_position(symbol, other_half)
                        print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                        return
                    else:
                        close_position(symbol, qty)
                        print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                        return

                await asyncio.sleep(1)
                if any(bd is None for bd in [vwap, stdev, close_5m, timestamp_5m]):
                    continue

                if vwap*1.125 <= close_5m < vwap*1.150: # 12.5 - 15.0%, tweak
                    if not take_50:
                        take_50 = True
                        close_position(symbol, half_position)
                        print(f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, 50% Exit, {half_position}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                        break
                    else:
                        close_position(symbol, other_half)
                        print(f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, 2nd 50% Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                        return
                if close_5m >= vwap*1.150: # 15.0%, tweak
                    if not take_50:
                        close_position(symbol, qty) # 100% take profit
                        print(f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, 100% Exit, {half_position}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                        return
                    else:
                        close_position(symbol, other_half)
                        print(f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                        async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                            await file.write(f"{now}, {symbol}, 2nd 50% Exit, {qty}, {price}" + "\n")
                        pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                        return
                else:
                    while True:
                        vwap2, stdev2, close_5m2, high_5m2, timestamp_5m2 = get_bar_data(symbol)
                        
                        if any(bd2 is None for bd2 in [vwap2, stdev2, close_5m2, high_5m2, timestamp_5m2]):
                            continue

                        if timestamp_5m2 != timestamp_5m:
                            break

                        await asyncio.sleep(1)
                    
                await asyncio.sleep(1)


        except Exception as e:
            print(f"[{symbol}] Error: {e}", flush=True)
            # check systemd logs for traceback...
            traceback.print_exc()
            await stop_price_quote_bar_stream(symbol)
        

        await asyncio.sleep(1)


async def supervisor(coro_func, *args, name="task"):
    # while True: # looping to restart after 5s risks getting stuck in an enter, fail, enter, fail... loop - needs global variables
        try:
            await coro_func(*args)
        except Exception as e:
            print(f"{name} crashed: {e}")
            # await asyncio.sleep(5)

async def main():
    try:
        data_stream_task = asyncio.create_task(supervisor(start_price_quote_bar_stream, symbols, name="data_stream"))
        monitor_tasks = [
            asyncio.create_task(
                supervisor(monitor_trade, setup, name=f"monitor_trade-{setup['symbol']}")
            ) 
            for setup in cached_configs
        ]
        await asyncio.gather(data_stream_task, *monitor_tasks)
    except asyncio.CancelledError:
        print("Error, tasks cancelled")
    finally:
        await handle_shutdown()

# systemctl stop / ctrl+c cleanup
async def handle_shutdown():
    print("Shutting down...")

    for symbol in symbols:
        await stop_price_quote_bar_stream(symbol)
    await stock_stream.stop_ws()

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    print("Cleanup complete. Exiting...")


def main_start():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(handle_shutdown()))

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
        print("Event loop closed")


if __name__ == "__main__":
    main_start()

