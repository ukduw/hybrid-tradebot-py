from alpaca.data.live import StockDataStream
from alpaca.data.models import Trade
from alpaca.data.enums import DataFeed

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import pandas as pd
import pandas_ta as ta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType

import datetime, time, pytz
from decimal import Decimal, ROUND_UP, ROUND_DOWN
from collections import defaultdict, deque
from dataclasses import dataclass

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
USE_PAPER_TRADING = os.getenv("USE_PAPER_TRADING")

latest_prices = {}
day_high = {}
latest_macd = {}

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)

historical_client = StockHistoricalDataClient(api_key=API_KEY, secret_key=SECRET_KEY)
trading_client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=USE_PAPER_TRADING)
stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)


# ===== WEBSOCKETS, DATA STREAM HANDLERS ===== #
@dataclass
class QuoteEntry:
    bid: float
    ask: float
    timestamp: datetime.datetime

class DataHandler:
    def __init__(self):
        self.quote_window = defaultdict(lambda: deque(maxlen=500))
        self.bar_window = defaultdict(lambda: deque(maxlen=200))

    async def handle_quote(self, quote):
        self.quote_window[quote.symbol].append(
            QuoteEntry(
                bid=quote.bid_price,
                ask=quote.ask_price,
                timestamp=quote.timestamp
            )
        )

    async def handle_trade(self, trade: Trade):
        symbol = trade.symbol
        trade_time = trade.timestamp
        trade_price = trade.price

        quotes = self.quote_window.get(symbol, [])
        if not quotes:
            with open(f"price-stream-logs/price_stream_log_{trade.symbol}.txt", "a") as file:
                file.write(f"[GHOST] {now},{trade.symbol},PRICE {trade.price},VOL {trade.size}, COND {trade.conditions}" + "\n")
            return
        
        closest_quote = min(quotes, key=lambda q: abs((q.timestamp - trade_time).total_seconds()))
        if abs((closest_quote.timestamp - trade_time).total_seconds()) > 1:
            with open(f"price-stream-logs/price_stream_log_{trade.symbol}.txt", "a") as file:
                file.write(f"[GHOST] {now},{trade.symbol},PRICE {trade.price},VOL {trade.size}, COND {trade.conditions}" + "\n")
            return  
        
        tolerance = 0.02 # 2.0%
        if not (closest_quote.bid * (1 - tolerance) <= trade_price <= closest_quote.ask * (1 - tolerance)):
            with open(f"price-stream-logs/price_stream_log_{trade.symbol}.txt", "a") as file:
                file.write(f"[GHOST] {now},{trade.symbol},PRICE {trade.price},VOL {trade.size}, COND {trade.conditions}" + "\n")
            return

        if trade.size < 100:
            with open(f"price-stream-logs/price_stream_log_{trade.symbol}.txt", "a") as file:
                file.write(f"[GHOST] {now},{trade.symbol},PRICE {trade.price},VOL {trade.size}, COND {trade.conditions}" + "\n")
            return
        
        # if all conditions pass:
        latest_prices[symbol] = trade_price
        if symbol not in day_high or trade_price > day_high[symbol]:
            day_high[symbol] = trade_price

        # print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

        with open(f"price-stream-logs/price_stream_log_{trade.symbol}.txt", "a") as file:
            file.write(f"{now},{trade.symbol},PRICE {trade.price},VOL {trade.size}, COND {trade.conditions}" + "\n")

    async def handle_bar(self, bar):
        self.bar_window[bar.symbol].append(

        )


# ===== BAR DATA REQUESTS, INDICATOR GENERATION ===== #
    # keep indicator states per symbol
    # store indicator values over time, not just latest
    # update indicators as data from new bars is retrieved
    # function to retrieve values into main

    # MACD first; RSI may not be necessary
    # signal may also be unnecessary

class BarIndicatorHandler:
    def __init__(self):
        window_size = 100
        self.bar_window = defaultdict(lambda: deque(maxlen=window_size))
        self.macd_history = defaultdict(list)

    def fetch_seed_bars(symbol):
        lookback_minutes = 100
        start_time = now - datetime.timedelta(minutes=lookback_minutes + 10)

        request_params = StockBarsRequest(
            symbol=symbol,
            start=start_time,
            end=now,
            timeframe=TimeFrame.Minute
        )

        bars = historical_client.get_stock_bars(request_params=request_params).df
        df = bars[bars.index.get_level_values(0) == symbol].copy()
        df.reset_index(inplace=True)
        df.rename(columns={"timestamp": "datetime"}, inplace=True)
        df.set_index("datetime", inplace=True)
        return df

    def update_bar(self, bar):
        # PLACEHOLDER
        # PLACEHOLDER
        return
    
    def compute_macd(self, df):
        if "close" not in df.columns:
            return
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)

        if not macd.empty:
            self.macd_history[self.symbol].append({
                'macd': macd['MACD_12_26_9'].iloc[-1],
                'signal': macd['MACDs_12_26_9'].iloc[-1],
                'hist': macd['MACDh_12_26_9'].iloc[-1]
            })


# ===== OPEN/CLOSE STREAM, HANDLER CALL UTILS ===== #
handler = DataHandler()

async def start_price_quote_bar_stream(symbols):
    for symbol in symbols:
        await stock_stream.subscribe_trades(handler.handle_trade, symbol)
        await stock_stream.subscribe_quotes(handler.handle_quote, symbol)
        await stock_stream.subscribe_bars(handler.handle_bar, symbol)

    try:
        await stock_stream.run()
    except Exception as e:
        print(f"[WebSocket] Unexpected error: {e}")

async def stop_price_quote_bar_stream(symbol):
    try:
        await stock_stream.unsubscribe_trades(symbol)
        await stock_stream.unsubscribe_quotes(symbol)
        await stock_stream.unsubscribe_bars(symbol)
        print(f"[{symbol}] price/quote stream unsubscribed")
    except Exception as e:
        print (f"[WebSocket] Error unsubscribing from {symbol}: {e}")


# ===== VALUE RETRIEVAL UTILS (to main) ===== #
def get_current_price(symbol):
    return latest_prices.get(symbol)

def get_day_high(symbol):
    return day_high.get(symbol)

# def get_latest_macd(symbol)


# ===== TRADING CLIENT UTILS ===== #
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
            limit_price = float(Decimal(tick * 1.01).quantize(Decimal("0.01"), rounding=ROUND_UP)) if tick >= 1.00 else float(Decimal(tick * 1.01).quantize(Decimal("0.0001"), rounding=ROUND_UP)),
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
            type = OrderType.LIMIT,
            time_in_force = TimeInForce.DAY,
            limit_price = float(Decimal(tick * 0.99).quantize(Decimal("0.01"), rounding=ROUND_DOWN)) if tick >= 1.00 else float(Decimal(tick * 0.99).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)),
            extended_hours = True
        )
        order = trading_client.submit_order(order_data)
        return order
    else:
        return trading_client.close_position(symbol, qty)

def close_all_positions():
    try:
        results = trading_client.close_all_positions()    
        eastern = pytz.timezone("US/Eastern")
        now = datetime.datetime.now(eastern)
        for r in results:
            print(f"Closed: {r.symbol} - Qty: {r.qty}")
            with open("trade-log/trade_log.txt", "a") as file:
                file.write(f"{now}, {r.get('symbol')}, {r.get('qty')}, EOD Exit; break even" + "\n")
    except Exception as e:
        print(f"Failed to close positions: {e}")
