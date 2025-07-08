from alpaca.data.models import Trade

import json

with open("configs.json", "r") as f:
    configs_json = json.load(f)

in_position = {}

async def handle_trade(trade: Trade):
    symbol = trade.symbol
    price = trade.price
    print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

    if symbol not in in_position:
        in_position[symbol] = False

    #if not position_open[symbol] and price > entry (IMPORT CONFIG JSON):
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