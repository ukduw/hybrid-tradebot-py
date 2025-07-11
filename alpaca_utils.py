from alpaca.data.live import StockDataStream
from alpaca.data.models import Trade
from alpaca.data.enums import DataFeed

from alpaca.data.models import Bar
from alpaca.data.timeframe import TimeFrame

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.requests import LimitOrderRequest
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

trading_client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=USE_PAPER_TRADING)
stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)

async def handle_trade(trade: Trade):
    symbol = trade.symbol
    price = trade.price
    latest_prices[symbol] = price
    # print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

def start_price_stream(symbols):
    for symbol in symbols:
        stock_stream.subscribe_trades(handle_trade, symbol)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(stock_stream.run())
    except Exception as e:
        print(f"[WebSocket] Unexpected error: {e}")


def stop_price_stream(symbol):
    stock_stream.unsubscribe_trades(symbol)


def get_current_price(symbol):
    return latest_prices.get(symbol)


def is_premarket():
    eastern = pytz.timezone("US/Eastern")
    now = datetime.datetime.now(eastern).time()
    return (datetime.time(4,0) <= now < datetime.time(9, 30))

def place_order(symbol, qty):
    premarket = is_premarket()
    tick = get_current_price(symbol)

    if premarket:
        order_data = LimitOrderRequest(
            symbol = symbol,
            qty = qty,
            side = OrderSide.BUY,
            type = OrderType.LIMIT,
            time_in_force = TimeInForce.DAY,
            limit_price = tick * 1.02,
            extended_hours = True
        )
    else:
        order_data = MarketOrderRequest(
            symbol = symbol,
            qty = qty,
            side = OrderSide.BUY,
            type = OrderType.MARKET,
            time_in_force = TimeInForce.DAY,
            extended_hours = False
        )
    order = trading_client.submit_order(order_data)
    return order


def close_position(symbol, qty):
    premarket = is_premarket()
    tick = get_current_price(symbol)

    if premarket:
        order_data = LimitOrderRequest(
            symbol = symbol,
            qty = qty,
            side = OrderSide.SELL,
            type = OrderType.Limit,
            time_in_force = TimeInForce.DAY,
            limit_price = tick * 0.98,
            extended_hours = True
        )
        order = trading_client.submit_order(order_data)
        return order
    else:
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
