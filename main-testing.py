# TEST FILE FOR EVENT-DRIVEN REFACTOR


import threading, json
from handle_trade import start_price_stream


with open("configs.json", "r") as f:
    cached_configs = json.load(f)


symbols = [setup["symbol"] for setup in cached_configs]
threading.Thread(target=start_price_stream, args=(symbols,), daemon=True).start()


