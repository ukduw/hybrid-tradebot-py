## Install and Run:
`python3 -m venv venv`   
`source venv/bin/activate`

`pip install -r requirements.txt`

Make .env file:
```
API_KEY = "your-alpaca-api-key"
SECRET_KEY = "your-alpaca-secret-key"
USE_PAPER_TRADING = True # paper trading

PUSHBULLET_API_KEY = "your-pushbullet-api-key-here"
```
Sign up with Alpaca and Pushbullet for API keys; must download Pushbullet app to receive push notifications.   
NOTE: Alpaca's free market data is limited to IEX data only.   

NOTE: I've added a PDT rule protection that counts the number of day trades. It's currently limited to 1, so the user can spread their trades over 3 days. If this isn't needed, comment out these lines in main.py: 24-34, can_enter_trade() condition in line 75, and 83-85.   

Run config CLI (to input trade parameters):   
`python3 config_CLI.py`

Run hybrid bot:   
`python3 main.py`

NOTE: UPDATE/RE-WRITE README

## Hybrid Trading Bot
This project is made for traders with some experience and established strategies, as well as for new traders to use with paper trading to learn and experiment with new strategies. 

The Hybrid Trading Bot is a semi-automated bot which, rather than scanning a vast universe of stocks and automatically trading any stock that meets the user’s criteria, allows the user to specify entry and exit conditions and position size per ticker on a case-by-case basis. This allows the user to enter and exit multiple trades simultaneously and capture opportunities they had the right strategy for, but would otherwise have missed, and especially opportunities with time-sensitive trade executions. 

A trader cannot make 10 plays simultaneously or constantly be "on the ball" from 04:00 - 20:00 market time, but the bot can. **The user could work a full time job with a normal sleep schedule while the bot executes their strategies autonomously, literally from dawn till dusk.** The user would simply have to run a screener and set new conditions for the bot once a day after work. Emotional trading is also eliminated, ensuring that all trades are made strictly according to the user's strategies.

## Profit-Taking and Risk Management
Profit-taking is executed by the bot according to MACD and trailing stop strategies. 

First, the data is seeded at premarket open by fetching the last 100 15min candlestick closes. Then, the MACD is re-computed per symbol as new bar data comes in via the websocket/data stream. If the percentage difference between the MACD and Signal line is high enough, the highest percentage difference is tracked and profit is taken via trailing stop, which is triggered when the current percentage difference is lower than the high by 20% or more. Partial or full profit is taken depending on how high the percentage difference is. Percentage difference:
- ( MACD Histogram / Signal line ) * 100

NOTE: The specific profit-taking parameters are in lines 148 - 188 of main.py and can be tweaked or reversed depending on the user's strategy. The current parameters are suited for maximizing profit-taking during strength and locking in partial profits during runs for long strategies. 

The trailing stop allows winning plays to run and protects profits against downturns, while using MACD maximizes profit-taking during spikes only, avoiding early profit-taking.

Position size management is simplified. The user can input a different dollar amount per ticker. The program then determines each position size automatically: 
- Rounded Up(Dollar Value / Entry Price) = Quantity

## Gap Up Protection
If a stock gaps up above the user's entry condition, it must continue uptrending 1.5% above its open before any tick data is passed to the bot's logic. This prevents false signals/entries in the case of gap-up-sell-off price action, and means that the bot only acts on confirmed signals. Many gap ups result in sell-offs or consolidation below their market open. In these cases, the entry may be significantly above the user's inputted entry condition, resulting in a higher risk level and % loss than intended when it is stopped out.

## Websocket Tick Data Filter
There is a filter on the tick data that comes through the Alpaca websocket. A scrolling window (a deque) of quotes is streamed via the websocket. Each tick is compared with the closest-timestamp quotes and prevented from being passed to the bot's decision-making logic if it is outside of a 2% tolerance. Odd lot trades (<100 volume) are also ignored by the bot. These measures are to prevent "ghost ticks" from triggering entry/exit conditions falsely. These "ghost ticks" that are technically real, but typically filtered out by charting software by various means, making entries/exits triggered by these "ghost ticks" appear completely erroneous.

NOTE: the tolerance % can be adjusted in line 101 of alpaca_utils.py - the 2% tolerance is suited for low priced stocks, where large relative spreads are normal.

## Trade Log Export and Push Notifications
Entry and exit data are piped to a text file for easy export. The user can utilize this to generate statistics and optimize their strategies or to experiment with new strategies.

Push notifications are sent to the user's phone on entry/exit so the user can monitor the bot's activity throughout the day. The notifications contain the ticker, number of shares, order type, entry/exit point:
- e.g. "50 AAPL Market buy placed at $203.53"


&nbsp;
---
Currently uses CLI for user config inputs.   

The configs json to be changed in real time, so trade parameters can be changed/removed as each setup develops.