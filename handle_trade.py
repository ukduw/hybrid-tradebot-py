from alpaca.data.models import Trade


async def handle_trade(trade: Trade):
    symbol = trade.symbol
    price = trade.price
    
    print(f"[WebSocket] {trade.symbol} @ {trade.price}") # comment out while not testing

    #if condition:
        # await place_order(symbol)
    # elif condition:
        # ...





# in main.py:

# for symbol in symbols:
    # stock_stream.subscribe_trades(handle_trade, symbol)