import requests
import datetime, pytz
import csv

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

def get_current_price(symbol):
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
    headers = HEADERS.copy()
    headers["accept"] = "application/json"
    response = requests.get(url, headers=headers)
    return float(response.json()["quotes"]["ap"])

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

