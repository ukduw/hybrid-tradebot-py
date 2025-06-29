from alpaca.data.live import StockDataStream
from alpaca.data.timeframe import TimeFrame
from alpaca.data.models import Bar

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType

import asyncio

import datetime, pytz
import csv

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
USE_PAPER_TRADING = os.getenv("USE_PAPER_TRADING")

latest_prices = {}

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=USE_PAPER_TRADING)
stock_stream = StockDataStream(API_KEY, SECRET_KEY, feed='sip') # iex for free data...

async def handle_bar(bar: Bar):
    symbol = bar.symbol
    price = bar.close
    latest_prices[symbol] = price
    print(f"[BAR] {symbol}: {price} @ {bar.timestamp}") # take out after testing

def start_price_stream(symbols):
    for symbol in symbols:
        stock_stream.subscribe_bars(handle_bar, symbol, TimeFrame.Second)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(stock_stream.run())

def get_current_price(symbol):
    return latest_prices.get(symbol)


def place_order(symbol, qty):
    order_data = MarketOrderRequest(
        symbol = symbol,
        qty = qty,
        side = OrderSide.BUY,
        type = OrderType.MARKET,
        time_in_force = TimeInForce.GTC
    )
    order = trading_client.submit_order(order_data)
    return order

def close_position(symbol):
    return trading_client.close_position(symbol)

def close_all_positions():
    try:
        results = trading_client.close_all_positions()    
        eastern = pytz.timezone("US/Eastern")
        now = datetime.datetime.now(eastern)
        for r in results:
            print(f"Closed: {r.symbol} - Qty: {r.qty}")
            with open("trade_log", mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(f"{now}, {r.get('symbol')}, {r.get('qty')}, EOD Exit; break even")
    except Exception as e:
        print(f"Failed to close positions: {e}")
