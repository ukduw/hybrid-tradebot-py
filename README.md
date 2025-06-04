## Install and Run:
placeholder   
placeholder   

## Hybrid Trading Bot
This project is made for traders with some experience and established strategies, as well as for new traders to use with paper trading to learn and experiment with new strategies. 

The Hybrid Trading Bot is a semi-automated bot which, rather than screening the entire universe of stocks for any setup that matches the user's conditions, functions on a case by case basis. It requires the user to specify entry and exit conditions and profit-taking and stop-loss logic on a per ticker basis. 

A trader cannot make 10 plays simultaneously or constantly be "on the ball" from 04:00 - 20:00 market time, but the bot can. This allows traders to capture opportunities that they had the right strategy for but would otherwise have missed. 

**The user could work a full time job with a normal sleep schedule while the bot executes their strategies autonomously, literally from dawn till dusk.** The user would simply have to run a screener and set new conditions for the bot once a day after work. Emotional trading is also eliminated, ensuring that all trades are made strictly according to the user's strategies.

## Profit-Taking and Risk Management
Trailing stop-loss logic allows winning plays to run, protecting profits against downturns. The default setting is for the trailing stop to only activate when the %Change is 15% over the entry. This is to allow for fluctuations around the entry price, where the only price action that should result in an exit is the stop-loss being hit. The trailing stop-loss is a profit-taking measure that should only activate if the ticker is a confirmed winner. These settings can be changed/removed to suit different strategies.

Position size management is simplified. The user can input a different dollar amount per ticker. The program then determines each position size automatically: 
- Rounded Up(Dollar Value / Entry Price) = Quantity

## CSV Export and Push Notifications
Entry and exit data are piped to a CSV file for easy export. The user can utilize this to generate statistics and optimize their strategies or to experiment with new strategies.

Push notifications are sent to the user's phone on entry/exit so the user can monitor the bot's activity throughout the day. The notifications contain the ticker, number of shares, order type, entry/exit point:
- e.g. "50 AAPL Market buy placed at $203.53"

