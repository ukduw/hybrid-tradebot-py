from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import QuoteLatestRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType

import datetime, pytz
import csv

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
LIVE_TRADING = os.getenv("LIVE_TRADING")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=LIVE_TRADING)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

def get_current_price(symbol):
    request = QuoteLatestRequest(symbol_or_symbols=symbol)
    latest_quote = data_client.get_stock_latest_quote(request)
    return float(latest_quote[symbol].askprice)

def place_order(symbol, qty, side="buy"):
    order = {
        "symbol": symbol, 
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "gtc"
    }
    response = requests.post(f"{BASE_URL}/v2/orders", json=order, headers=HEADERS)
    return response.json()

def close_position(symbol):
    url = f"{BASE_URL}/v2/positions/{symbol}"
    return requests.delete(url, headers=HEADERS).json()

def close_all_positions():
    url = f"{BASE_URL}/v2/positions"
    response = requests.delete(url, headers=HEADERS)

    if response.status_code == 207:
        print("!!! Partial success closing positions")
    elif response.status_code == 200:
        print("All positions closed.")
    else:
        print(f"Failsed to close positions: {response.status_code} {response.text}")

    if response.status_code in [200, 207]:
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)
        results = response.json()
        for r in results:
            print(f"Closed: {r.get('symbol')} - Qty: {r.get('qty')}")
            with open("trade_log", mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(f"{now}, {r.get('symbol')}, {r.get('qty')}, EOD Exit; break even")

