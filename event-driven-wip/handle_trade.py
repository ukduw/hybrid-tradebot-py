from alpaca.data.models import Trade
from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.data.enums import DataFeed

import json, math, pytz, datetime, threading, asyncio

from pushbullet import Pushbullet
from dotenv import load_dotenv
import os

from alpaca_utils_testing import close_all_positions, stop_price_stream
from alpaca_utils_testing import place_order, close_position

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=15, minute=55, second=0, microsecond=0)

with open("configs.json", "r") as f:
    configs_json = json.load(f)

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
USE_PAPER_TRADING = os.getenv("USE_PAPER_TRADING")

PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")
pb = Pushbullet(PB_API_KEY)

trading_client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=USE_PAPER_TRADING)
stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)

in_position = {}

day_trade_counter = 0
day_trade_lock = threading.Lock()
        


async def handle_trade(trade: Trade):
    symbol = trade.symbol
    price = trade.price
    print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

    entry = configs_json["entry_price"]
    stop = configs_json["stop_loss"]
    trailing_stop = configs_json["trailing_stop_percentage"]
    qty = math.ceil(configs_json["dollar_value"] / configs_json["entry_price"])
    day_high = entry

    if symbol not in in_position:
        in_position[symbol] = False

    now = datetime.datetime.now(eastern)
    if now >= exit_open_positions_at:
        close_all_positions()
        print("End of day - all positions closed.")
        stop_price_stream(symbol)
        return


    if not in_position[symbol]:
        global day_trade_counter
        if day_trade_counter < 1 and price > entry:
            with day_trade_lock:
                if day_trade_counter < 1:
                    place_order(symbol, qty)
                    print(f"{qty} [{symbol}] BUY @ {price}")
                    in_position[symbol] = True
                    day_trade_counter += 1
                    with open("trade-log/trade_log.txt", "a") as file:
                        file.write(f"{now},{symbol},Entry,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"{qty} [{symbol}] BUY @ {price}")
        elif not day_trade_counter < 1 and price > entry:
            print(f"Skipped [{symbol}] @ {price}, PDT limit hit...")
            stop_price_stream(symbol)
            with open("trade-log/trade_log.txt", "a") as file:
                file.write(f"{now},{symbol},SKIP,{qty},{price}" + "\n")
            return

    if in_position[symbol]:
        if price < stop: 
            close_position(symbol, qty)
            print(f"[{symbol}] stop-loss hit. Exiting.")
            with open("trade-log/trade_log.txt", "a") as file:
                file.write(f"{now},{symbol},Exit,{qty},{price}" + "\n")
            pb.push_note("Hybrid bot", f"[{symbol}] stop-loss hit. Exiting.")
            return
        else:
            if price > day_high:
                day_high = price
            if day_high >= entry * 1.15 and price <= day_high * (100 - trailing_stop)/100:
                close_position(symbol, qty)
                print(f"[{symbol}] take-profit hit. Exiting.")
                with open("trade-log/trade_log.txt", "a") as file:
                    file.write(f"{now}, {symbol}, Exit, {qty}, {price}" + "\n")
                pb.push_note("Hybrid bot", f"[{symbol}] take-profit hit. Exiting.")
                return


def start_price_stream(symbols):
    for symbol in symbols:
        stock_stream.subscribe_trades(handle_trade, symbol)
        print(f"[{symbol}] Monitoring...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(stock_stream.run())
    except Exception as e:
        print(f"[WebSocket] Unexpected error: {e}")





# how to deal with config updates...?