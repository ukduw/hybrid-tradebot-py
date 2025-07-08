# TEST FILE FOR EVENT-DRIVEN REFACTOR


import threading
from handle_trade import start_price_stream



symbols = [setup["symbol"] for setup in cached_configs]
threading.Thread(target=start_price_stream, args=(symbols,), daemon=True).start()


