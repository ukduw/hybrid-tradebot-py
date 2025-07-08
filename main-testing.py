# TEST FILE FOR EVENT-DRIVEN REFACTOR


import threading
import 



symbols = [setup["symbol"] for setup in cached_configs]
threading.Thread(target=start_price_stream, args=(symbols,), daemon=True).start()


    
for setup in cached_configs:
    t = threading.Thread(target=monitor_trade, args=(setup,))
    t.start()