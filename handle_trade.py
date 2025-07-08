from alpaca.data.models import Trade

import json, math, pytz, datetime, threading

eastern = pytz.timezone("US/Eastern")
now = datetime.datetime.now(eastern)
exit_open_positions_at = now.replace(hour=15, minute=55, second=0, microsecond=0)

with open("configs.json", "r") as f:
    configs_json = json.load(f)

in_position = {}

day_trade_counter = 0
day_trade_lock = threading.Lock()

def can_enter_trade():
    global day_trade_counter
    with day_trade_lock:
        if day_trade_counter < 1:
            day_trade_counter += 1
            return True
        else: 
            return False
        

async def handle_trade(trade: Trade):
    symbol = trade.symbol
    price = trade.price
    print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

    entry = configs_json["entry_price"]
    stop = configs_json["stop_loss"]
    trailing_stop = configs_json["trailing_stop_percentage"]
    qty = math.ceil(configs_json["dollar_value"] / configs_json["entry_price"])
    day_high = entry

    if price > day_high:
        day_high = price

    if symbol not in in_position:
        in_position[symbol] = False

    #if not position_open[symbol] and can_enter_trade() and price > entry:
        # await place_order(symbol)
        # print(f"{qty} [{symbol}] Market buy placed at {price}")
        # in_position[symbol] = True
    # elif condition:
        # ...




# in main.py:

# for symbol in symbols:
    # stock_stream.subscribe_trades(handle_trade, symbol)
# or just use start_price_stream...



# how to deal with config updates...?