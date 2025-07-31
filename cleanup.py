from alpaca.data.live import StockDataStream
from alpaca.data.enums import DataFeed

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY, feed=DataFeed.SIP)

async def main():
    try:
        print("Running cleanup...")
        await stock_stream.unsubscribe_all()
        await stock_stream.stop_ws()
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())