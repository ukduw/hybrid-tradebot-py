import asyncio
import websockets
import json
import threading

from dotenv import load_dotenv
import os

load_dotenv()
FINNHUB_TOKEN = os.getenv("FINNHUB_TOKEN")
FINNHUB_WS_URL = f"wss://ws.finnhub.io?token={FINNHUB_TOKEN}"


class PriceStream:
    def __init__(self, symbols):
        self.symbols = symbols
        self.latest_prices = {symbol: None for symbol in symbols}
        self.lock = threading.Lock()
        self.ws = None
    
    async def _connect(self):
        async with websockets.connect(FINNHUB_WS_URL) as websocket:
            self.ws = websocket
            await self._subscribe_symbols()
            await self._handle_messages()

    async def _subscribe_symbols(self):
        for symbol in self.symbols:
            await self.ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))

    async def _handle_messages(self):
        while True:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                if data["type"] == "trade":
                    for t in data["data"]:
                        symbol = t["s"]
                        price = t["p"]
                        with self.lock:
                            self.latest_prices[symbol] = price
            except Exception as e:
                print("WebSocket error: ", e)
                break
        
    def start(self):
        threading.Thread(target=self._start_loop, daemon=True).start()
    
    def _start_loop(self):
        asyncio.new_event_loop().run_until_complete(self._connect())
    
    def get_current_price(self, symbol):
        with self.lock:
            return self.latest_prices.get(symbol)

