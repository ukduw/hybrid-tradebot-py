from alpaca.data.live import StockDataStream
from alpaca.data.models import Trade
from alpaca.data.enums import DataFeed

from alpaca.trading.client import TradingClient

import asyncio
import time

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
USE_PAPER_TRADING = os.getenv("USE_PAPER_TRADING")


trading_client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=USE_PAPER_TRADING)
stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)

async def handle_trade(trade: Trade):
    print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

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
    if symbol in stock_stream._handlers.get("trades", {}):
        stock_stream.unsubscribe_trades(symbol)
        print(f"[{symbol}] price stream unsubscribed")



if __name__ == "__main__":
    start_price_stream("BKKT") # change for testing
    time.sleep(120)
    stop_price_stream("BKKT")