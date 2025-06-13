import json
import datetime, pytz

CONFIG_FILE = "configs.json"

eastern = pytz.timezone("US/Eastern")
with_time = datetime.datetime.now(eastern)
split = str(with_time).split(" ")
now = split[0]


def prompt_configs(defaults=None):
    if defaults is None:
        defaults = {
            "trailing_stop_percentage": 5,
            "dollar_value": 5000
        }

    symbol = input(f"Stock symbol: ").upper()
    entry = input(f"Entry price: ")
    stop = input(f"Stop-loss price: ")
    trailing_stop_percentage = input(f"Trailing stop % [{defaults['trailing_stop_percentage']}]: ")
    dollar_value = input(f"Position dollar value [{defaults['dollar_value']}]: ")

    return {
        "symbol": symbol,
        "entry_price": float(entry),
        "stop_loss": float(stop),
        "trailing_stop_percentage": float(trailing_stop_percentage or defaults['trailing_stop_percentage']),
        "dollar_value": float(dollar_value or defaults['dollar_value'])
    }

def main():
    print("Input trade config")
    configs = []

    while True:
        trade = prompt_configs()
        configs.append(trade)
        cont = input("Add another trade? (y/n): ").strip().lower()
        if cont != "y":
            break

    with open(CONFIG_FILE, "w") as file:
        json.dump(configs, file, indent=2)
    
    with open("config-log/config-log.txt", mode="a", newline="") as log:
        for c in configs:
            log.write("\n" + f"{now},{c['symbol']},{c['entry_price']},{c['stop_loss']},{c['trailing_stop_percentage']},{c['dollar_value']}")
    
    print("New configs saved to configs.json: ")
    for c in configs:
        print(f" - {c['symbol']}: Entry {c['entry_price']}, Stop {c['stop_loss']}, Trail {c['trailing_stop_percentage']}%, Qty ${c['dollar_value']}")

if __name__ == "__main__":
    main()


