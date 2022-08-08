
# Long-short trading strategy with FTSE 100 ETF (ISF.L) using Keltner Channels (K-Band)
# Part 2 (adding stop loss)

### Loading libraries
import yfinance as yf
import ta
import pandas as pd
from datetime import date, timedelta, datetime

### Importing data
ticker = 'ISF.L'
# ticker = 'NVDA' #NVDA not performing as well, with a negative 36.67% cumulative return
start_date = '2019-01-01'
end_date = '2019-12-31'

date_fmt = '%Y-%m-%d'

start_date_buffer = datetime.strptime(start_date, date_fmt) - timedelta(days = 365)
start_date_buffer = start_date_buffer.strftime(date_fmt)
start_date_buffer

### downloading data with yahoo finance
df = yf.download(ticker, start = start_date, end = end_date)
df.head()

### Keltner Channel calculation
k_band = ta.volatility.KeltnerChannel(df.High, df.Low, df.Close, 10, 10)

df['K_BAND_UB'] = k_band.keltner_channel_hband().round(4)
df['K_BAND_LB'] = k_band.keltner_channel_lband().round(4)

### Developing a trading strategy
'''
Our Strategy will be as follows:
Enter Long when close cross below the K-Band lower bound
Enter Short when close cross above the K-Band upper bound
Exit Position when there’s an opposite signal
'''
df['CLOSE_PREV'] = df.Close.shift(1)
df['LONG'] = (df.Close <= df.K_BAND_LB) & (df.CLOSE_PREV > df.K_BAND_LB) 
df['EXIT_LONG'] = (df.Close >= df.K_BAND_UB) & (df.CLOSE_PREV < df.K_BAND_UB) 

df['SHORT'] = (df.Close >= df.K_BAND_UB) & (df.CLOSE_PREV < df.K_BAND_UB) 
df['EXIT_SHORT'] = (df.Close <= df.K_BAND_LB) & (df.CLOSE_PREV > df.K_BAND_LB) 

'''
In real-world, when we see the trading signals, we will only be able to trade the next day, so the 
trades will happen the day after, i.e. we need to shift the signals by one day.
'''
df.LONG = df.LONG.shift(1)
df.EXIT_LONG = df.EXIT_LONG.shift(1)
df.SHORT = df.SHORT.shift(1)
df.EXIT_SHORT = df.EXIT_SHORT.shift(1)

df[['LONG', 'EXIT_LONG', 'SHORT', 'EXIT_SHORT']].dropna().head()

### Simulating trading in the year 2019

bt_df = df[(df.index >= start_date) & (df.index <= end_date)]

'''
We want to set up three things:
Initial Context: Start account balance, PnL (Profit and Loss) and positions.
Temporary Variables: the last signal indicating how to compute PnL, last price computing PnL and counter recording the days of trade.
Data to Analyze the Strategy: Trade dates, side, days, PnL, return and cumulative PnL.
'''

balance = 1000000
pnl = 0
position = 0

stop_loss_lvl = -2  # adding stop loss level

last_signal = 'hold'
last_price = 0
c = 0

trade_date_start = []
trade_date_end = []
trade_days = []
trade_side = []
trade_pnl = []
trade_ret = []

cum_value = []

'''
Within the loop, we will:
Exit Position if there’s a signal to exit.
Enter Position if there’s a signal to enter
Compute daily PnL, count trade days and record it
'''
'''
When we exit a trade, we need to do three things.
1) Compute the PnL of the trade and cash balance
2) Record trade stats such as the end date, days of trading and PnL
3) Reset the Temporary Variables such as trading day counter, position and last signal
    
The way to compute the PnL under either situation is the same. We also assume that we will use the Open price for trading 
(we will have the signal one day before). Notice, we used the Temporary Variables “last_price”, which we will record when entering the previous position.

The way to calculate the cash position will be different. For a long position, we sell the shares and take in the cash. We use the 
position and Open price to compute the market value and add that into the balance.

For a short position, we borrowed the shares and sold when entering the position, so we need to buy the shares back when exiting. In this case, 
we just need to update the balance with PnL.
'''

for index, row in bt_df.iterrows():
    
    # check and close any positions
    if row.EXIT_LONG and last_signal == 'long':
        trade_date_end.append(row.name)  # row.name and index correspond to the same thing
        trade_days.append(c)
        
        pnl = (row.Open - last_price) * position
        trade_pnl.append(pnl)
        trade_ret.append((row.Open / last_price - 1) * 100)
        
        balance = balance + row.Open * position  # on the long side, we add to the balance price at which we exit the trade (row.Open) * position
        
        position = 0
        last_signal = 'hold'       
        c = 0
        
    elif row.EXIT_SHORT and last_signal == 'short':
        trade_date_end.append(row.name)
        trade_days.append(c)
        
        pnl = (row.Open - last_price) * position
        trade_pnl.append(pnl)
        trade_ret.append((last_price / row.Open - 1) * 100)
        
        balance = balance + pnl  # on the short side, since we borrowed shares, we only add pnl amount
        
        position = 0
        last_signal = 'hold'       
        c = 0
    
    if row.LONG and last_signal != 'long':
        last_signal = 'long'
        last_price = row.Open
        trade_date_start.append(row.name)
        trade_side.append('long')
        
        position = int(balance / row.Open)
        cost = position * row.Open
        balance = balance - cost  # on the long side, when we open a trade, we compute the possible number of share we can buy and compute the cost to deduct from the current balance
        c = 0
    
    elif row.SHORT and last_signal != 'short':
        last_signal = 'short'
        last_price = row.Open
        trade_date_start.append(row.name)
        trade_side.append('short')
        
        position = int(balance / row.Open) * -1   # on the short side, we don't reduce our balance when we open the trade since we borrow shares. We just need to compute the number of shares we could borrow (we assume we can only borrow up to the cash balance we have)
        c = 0        
    
    # checking stop loss for the long position - new part of the code (part 2)
    if last_signal == 'long' and c > 0 and (row.Low / last_price - 1) * 100 <= stop_loss_lvl:  # to trigger a stop loss from a long trade, 3 conditions need to be met: we are in a long position, we held position for at least 1 day, and daily low is lower than our stop loss level
        # recording the trade
        c = c+1
        trade_date_end.append(row.name)  
        trade_days.append(c)
        
        stop_loss_price = last_price + round(last_price * (stop_loss_lvl / 100), 4)  # computing stop loss price
        
        # updating balance
        pnl = (stop_loss_price - last_price) * position
        trade_pnl.append(pnl)
        trade_ret.append((stop_loss_price / last_price -1) * 100)
        
        balance = balance + stop_loss_price * position
        
        # resetting temp variables
        position = 0 
        last_signal = 'hold'
        c = 0
    # checking stop loss for the short position - new part of the code (part 2)    
    elif last_signal == 'short' and c > 0 and (last_price / row.High - 1) * 100 <= stop_loss_lvl:  # to trigger a stop loss from a short trade, 3 conditions need to be met: we are in a short position, we held position for at least 1 day, and daily high is higher than our stop loss level
        # recording the trade
        c = c+1
        trade_date_end.append(row.name)  
        trade_days.append(c)
        
        stop_loss_price = last_price - round(last_price * (stop_loss_lvl / 100), 4)  # computing stop loss price
        
        # updating balance
        pnl = (stop_loss_price - last_price) * position
        trade_pnl.append(pnl)
        trade_ret.append((last_price / stop_loss_price -1) * 100)
        
        balance = balance + pnl
        
        # resetting temp variables
        position = 0 
        last_signal = 'hold'
        c = 0    
    
    
    # compute market value and count days for any possible position
    '''
    There are three possible situations:
        1) We are not in any position, nothing changes. Market value will be the cash balance we have.
        2) If we are in a long position, we then increase the day count by one and compute the market value. 
           We use the position times the Close price plus the existing cash balance.
        3) If we are in a short position. we will increase the day count by one too. To compute the market value, 
           we will calculate the PnL (difference of the Close price and last trading price times the positions). 
           It will then increase or decrease the existing balance accordingly.
    '''   
    if last_signal == 'hold':
        market_value = balance
    elif last_signal == 'long':
        c = c + 1
        market_value = position * row.Close + balance
    else:
        c = c + 1
        market_value = (row.Close - last_price) * position + balance
    
    cum_value.append(market_value)

### Backtest results
'''
We'd like to see 2 things:
1) Comparing with buy and hold strategy (i.e. do nothing), is our strategy getting us much more returns?
2) Is our strategy feasible? Will we have too many trades (i.e. increasing the trading cost)? Is the outperformance coming 
   from one or two single trades (i.e. quality of the signal)?
'''
cum_ret_df = pd.DataFrame(cum_value, index = bt_df.index, columns = ['CUM_RET'])
cum_ret_df['CUM_RET'] = (cum_ret_df.CUM_RET / 1000000 - 1) * 100
cum_ret_df['BUY_HOLD'] = (bt_df.Close / bt_df.Open.iloc[0] - 1) * 100
cum_ret_df['ZERO'] = 0
cum_ret_df.plot(figsize = (15, 5))

cum_ret_df.iloc[[-1]].round(2)
'''
We can see in 2019, our K-Band trading strategy worked well for ISF.L, which is ETF for the FTSE 100 index. However, by adding stop loss,
our performance declined from 41% to 39.5%.
This is not surprising, because -2% stop loss level is too sensitive. In reality, with the stock market, the level should be higher. We could 
try longer periods or higher level for experiments, which we will cover in the future.
From the chart we can see the trading strategy we have is not too volatile.
'''

### Pulling all stats into one table
size = min(len(trade_date_start), len(trade_date_end))

trade_dict = { 'START': trade_date_start[:size], 'END': trade_date_end[:size], 
              'SIDE': trade_side[:size], 'DAYS': trade_days[:size], 
              'PNL': trade_pnl[:size], 'RET': trade_ret[:size]
              }

trade_df = pd.DataFrame(trade_dict)
trade_df.head()

### Computing stats
num_trades = trade_df.groupby('SIDE').count()[['START']]
num_trades_win = trade_df[trade_df.PNL > 0].groupby('SIDE').count()[['START']]

avg_days = trade_df.groupby('SIDE').mean()[['DAYS']]

avg_ret = trade_df.groupby('SIDE').mean()[['RET']]
avg_ret_win = trade_df[trade_df.PNL > 0].groupby('SIDE').mean()[['RET']]
avg_ret_loss = trade_df[trade_df.PNL < 0].groupby('SIDE').mean()[['RET']]

std_ret = trade_df.groupby('SIDE').std()[['RET']]

detail_df = pd.concat([num_trades, num_trades_win, avg_days, avg_ret, avg_ret_win, avg_ret_loss, std_ret], axis = 1, sort = False)

detail_df.columns = ['NUM_TRADES', 'NUM_TRADES_WIN', 'AVG_DAYS', 'AVG_RET', 'AVG_RET_WIN', 'AVG_RET_LOSS', 'STD_RET']

detail_df.round(2)

### Adding maximum drawdown (new part of the code in part 2)
mv_df = pd.DataFrame(cum_value, index = bt_df.index, columns = ['MV'])
mv_df.head()

# calculating rolling maximum value
days = len(mv_df)

roll_max = mv_df.MV.rolling(window = days, min_periods  = 1).max()
drawdown_val = mv_df.MV - roll_max
drawdown_pct = (mv_df.MV / roll_max - 1) * 100

print('Max Drawdown Value:', round(drawdown_val.min(), 0))
print('Max Drawdown %', round(drawdown_pct.min(), 2))
'''
With our strategy, the maximum drawdown is -3.95%, which is good considering the general volatility of the stock market.

We could use it to analyze the strategy without stop loss too and we will find without stop loss, our maximum drawdown will be over -4%,
which means it’s riskier. But using less than 1% risk to get 2% more performance may be a good trade-off.
''' 
