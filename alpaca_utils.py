import requests
from alpaca_keys import API_KEY, SECRET_KEY, BASE_URL

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