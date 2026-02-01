import time
import requests
import pytz
import datetime

from pushbullet import Pushbullet

from dotenv import load_dotenv
import os

load_dotenv()

PB_API_KEY = os.getenv("PUSHBULLET_API_KEY")

class DummyPB:
    def push_note(self, title, body):
        print(f"(PB Failed) Unsent notification: {title}, {body}")

pb = DummyPB()

pb_reconnect_tries = 0
while pb_reconnect_tries < 5:
    try:
        pb = Pushbullet(PB_API_KEY)
        break
    except requests.exceptions.ConnectionError as e:
        pb_reconnect_tries += 1
        print(f"PB connection failed({pb_reconnect_tries}/5), retrying in 10s...", e)
        time.sleep(10)


# intput format:
    # "{now}, {symbol}, ENTRY/EXIT/skip/EOD EXIT, {qty}, {price}"
    # ...

def daily_pl_calc():
    entry_exit = {}
    percs = []

    eastern = pytz.timezone("US/Eastern")
    now = datetime.datetime.now(eastern)
    today = now.date()

    with open("trade-log/trade_log.txt", "a") as file:
        lines = file.readlines()

    for l in lines:
        split_line = l.split(", ")
        split_line[0] = datetime.datetime.strptime(split_line[0].strip(), "%Y-%m-%d %H:%M:%S")
        
        if split_line[0].date() == today:
            if "ENTRY" in split_line[2]:
                entry_exit[split_line[1]] = [float(split_line[4])]
            if "EXIT" in split_line[2]:
                entry_exit[split_line[1]].append(float(split_line[4]))

    for coin in entry_exit:
        pl = round( ( coin[1] / coin[0] - 1 ) * 100, 1 )
        percs.append(pl)
        entry_exit[coin].append(pl)

    total_trades = len(percs)
    total_pl = sum(percs)
    

    pb.push_note("Stock P/L", f"{total_pl}% ({total_trades}): {", ".join(f"{key}: {item[2]}" for key, item in entry_exit.items())}")
    print(f"{total_pl}% ({total_trades}): {", ".join(f"{key}: {item[2]}" for key, item in entry_exit.items())}")


# output format:
    # +5.0%, -1.6%, +3.4%...
    # total (additive): x%


if __name__ == "__main__":
    daily_pl_calc()

