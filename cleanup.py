from alpaca.data.live import StockDataStream
from alpaca.data.enums import DataFeed

from dotenv import load_dotenv
import os
import json
import sys

from alpaca_utils import stop_price_stream

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)


CONFIG_PATH = "configs.json"
with open("configs.json", "r") as f:
    configs_json = json.load(f)

symbols = [setup["symbol"] for setup in configs_json]


async def main():
    try:
        print("Running cleanup...")
        for symbol in symbols:
            await stop_price_stream(symbol)
        await stock_stream.stop_ws()

    except Exception as e:
        print(f"Cleanup error: {e}")
    finally:
        print("Cleanup complete. Exiting...")
        sys.exit(0)
    

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


