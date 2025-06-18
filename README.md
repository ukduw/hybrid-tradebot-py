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

NOTE: I've added a PDT rule protection that counts the number of day trades. It's currently limited to 1, so the user can spread their trades over 3 days; the counter must be reset to 0 manually each day. If this isn't needed, comment out these lines in main.py: 24-34, can_enter_trade() condition in line 75, and 83-85.   

Run config CLI (to input trade parameters):   
`python3 config_CLI.py`

Run hybrid bot:   
`python3 main.py`

## Hybrid Trading Bot
This project is made for traders with some experience and established strategies, as well as for new traders to use with paper trading to learn and experiment with new strategies. 

The Hybrid Trading Bot is a semi-automated bot which, rather than scanning a vast universe of stocks and automatically trading any stock that meets the user’s criteria, this bot allows the user to specify entry and exit conditions, including profit goal and stop-loss, per ticker on a case-by-case basis. This allows the user to enter and exit multiple trades simultaneously and capture opportunities they had the right strategy for, but would otherwise have missed, and especially opportunities with time-sensitive trade executions. 

A trader cannot make 10 plays simultaneously or constantly be "on the ball" from 04:00 - 20:00 market time, but the bot can. **The user could work a full time job with a normal sleep schedule while the bot executes their strategies autonomously, literally from dawn till dusk.** The user would simply have to run a screener and set new conditions for the bot once a day after work. Emotional trading is also eliminated, ensuring that all trades are made strictly according to the user's strategies.

## Profit-Taking and Risk Management
Trailing stop-loss logic allows winning plays to run, protecting profits against downturns. The default setting is for the trailing stop to only activate when the %Change is 15% over the entry. This is to allow for fluctuations around the entry price, where the only price action that should result in an exit is the stop-loss being hit. The trailing stop-loss is a profit-taking measure that should only activate if the ticker is a confirmed winner. These settings can be changed/removed to suit different strategies.

Position size management is simplified. The user can input a different dollar amount per ticker. The program then determines each position size automatically: 
- Rounded Up(Dollar Value / Entry Price) = Quantity

## Trade Log Export and Push Notifications
Entry and exit data are piped to a text file for easy export. The user can utilize this to generate statistics and optimize their strategies or to experiment with new strategies.

Push notifications are sent to the user's phone on entry/exit so the user can monitor the bot's activity throughout the day. The notifications contain the ticker, number of shares, order type, entry/exit point:
- e.g. "50 AAPL Market buy placed at $203.53"


&nbsp;
---
Currently uses CLI for user config inputs.   
Ideally, GUI would have real-time candlestick charting, where users could simply click the chart to set entry and exit targets per stock.