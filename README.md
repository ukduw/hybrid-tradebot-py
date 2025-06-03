## Install and Run:
placeholder   
placeholder   

## Hybrid Trading Bot
This project is made for traders with some experience and established strategies, as well as for new traders to use with paper trading to learn and experiment with new strategies. 

The Hybrid Trading Bot is a semi-automated bot which, rather than screening the entire universe of stocks for any setup that matches the user's conditions, functions on a case by case basis. It requires the user to specify entry and exit conditions and profit-taking and stop-loss logic on a per ticker basis. 

A trader cannot make 10 plays simultaneously or constantly be "on the ball" from 04:00 - 20:00 market time, but the bot can. This allows traders to capture opportunities that they had the right strategy for but would otherwise have missed. 

**The user could work a full time job with a normal sleep schedule while the bot executes their strategies autonomously, literally from dawn till dusk.** The user would simply have to run a screener and set new conditions for the bot once a day after work.

The bot also simplifies position size management. The user can input a different dollar amount per position, allowing for per-ticker risk management. The program then determines the position size automatically by dividing the inputted dollar amount by the intraday price and rounding up. It also eliminates emotional trading and ensures that all trades are made strictly according to the user's strategies.

## Trade Statistics and Notifications
Entry and exit data are piped to a CSV file for easy export. The user can utilize this to generate statistics and optimize their strategies or to experiment with new strategies.

Notifications on entries and exits are sent to the user via Telegram, so the user can monitor the bot's activity throughout the day.

