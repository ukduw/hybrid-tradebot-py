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
while pb_reconnect_tries <= 5: # low due to risk of getting stuck in loop past premarket open...
    try:
        pb = Pushbullet(PB_API_KEY)
        break
    except requests.exceptions.ConnectionError as e:
        pb_reconnect_tries += 1
        print(f"PB connection failed({pb_reconnect_tries}/5), retrying in 10s...", e)
        time.sleep(10)


from alpaca_utils import start_price_quote_bar_stream, get_current_price, get_day_high, get_latest_macd, stop_price_quote_bar_stream, place_order, close_position, close_all_positions, stock_stream

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=15, minute=55, second=0, microsecond=0)


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
    # CONVERT FROM THREADING TO ASYNCIO...
        # run and test...
    # 1. TWEAK GHOST TICK + PROFIT TAKING PARAMETERS
        # run and test...
        # re-entry logic can wait till after PDT...
    # 2. PDT - GAP UP PARAMETERS
        # currently averaging 15-20 tick watchlists - try to reduce to <10-15

    # 3. WRITE RE-CONNECT LOGIC IN CASE OF NETWORK FAILURE
        # don't forget the traceback saved in a txt...
        # write reconnect logic for price streams + logs so they don't fail silently
    # 4. WRITE EVENT-DRIVEN VERSION
        # current version sufficient; low priority
        # event = asyncio.Event(), then price stream handler calls event.set() when data arrives...

# unrelated TODO: prevent opening new positions within x time of close


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
        day_high = get_day_high(symbol)
        if day_high is None:
            await asyncio.sleep(2)
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
                    async with day_trade_lock:
                        if day_trade_counter < 1:
                            place_order(symbol, qty)
                            print(f"{qty} [{symbol}] BUY @ {price}")
                            in_position = True
                            day_high = price
                            day_trade_counter += 1
                            async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                await file.write(f"{now},{symbol},ENTRY,{qty},{price}" + "\n")
                            pb.push_note("Hybrid bot", f"{qty} [{symbol}] BUY @ {price}")
                elif not day_trade_counter < 1 and price > entry:
                    print(f"Skipped [{symbol}] @ {price}, PDT limit hit...")
                    # stop_price_quote_bar_stream(symbol)
                    async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                        await file.write(f"{now},{symbol},skip,{qty},{price}" + "\n")
                    # return
                    await asyncio.sleep(18000)

                await asyncio.sleep(1)

            if in_position:
                macd = get_latest_macd(symbol)
                percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100 if macd['MACDs_12_26_9'] != 0 else 0
                macd_perc_high = None

                half_position = round(qty / 2)

                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                        await file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    return
                
                if 150 < percent_diff < 200: # TWEAK VALUES
                    macd_perc_high = percent_diff
                    while not percent_diff > 199:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100
                        
                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.8: # TWEAK TRAIL
                            if not take_50:
                                take_50 = True
                                qty = qty - half_position
                                close_position(symbol, half_position)
                                print(f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                    await file.write(f"{now}, {symbol}, 50% Exit, {half_position}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                break
                            else:
                                close_position(symbol, qty)
                                print(f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                    await file.write(f"{now}, {symbol}, 2nd 50% Exit, {qty}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                return
                            
                        await asyncio.sleep(1)

                if percent_diff > 199: # TWEAK VALUE
                    macd_perc_high = percent_diff
                    while True:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100

                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.8: # TWEAK TRAIL
                            close_position(symbol, qty)
                            print(f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                await file.write(f"{now}, {symbol}, 100% Exit, {half_position}, {price}" + "\n")
                            pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            return
                        
                        await asyncio.sleep(1)
                
                await asyncio.sleep(1)


        except Exception as e:
            print(f"[{symbol}] Error: {e}", flush=True)
            # check systemd logs for traceback...
            traceback.print_exc()
            stop_price_quote_bar_stream(symbol)
        

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
        data_stream_task = asyncio.create_task(supervisor(start_price_quote_bar_stream(symbols), "data_stream"))
        monitor_tasks = [asyncio.create_task(supervisor(monitor_trade(setup), f"monitor_trade-{setup['symbol']}") for setup in cached_configs)]
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

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
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

