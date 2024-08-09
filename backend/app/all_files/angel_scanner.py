from SmartApi import SmartConnect
import pandas as pd
import numpy as np
import time as tt
from config import *
import requests
from datetime import datetime, date, time, timedelta
import pyotp
import requests


totp = pyotp.TOTP(TOKEN).now()
obj = SmartConnect(api_key=API_KEY)
data = obj.generateSession(USER_NAME, PIN, totp)

refreshToken = data['data']['refreshToken']
res = obj.getProfile(refreshToken)
res['data']['exchanges']


url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
d = requests.get(url).json()
token_df = pd.DataFrame.from_dict(d)
token_df['expiry'] = pd.to_datetime(token_df['expiry']).apply(lambda x: x.date())
token_df = token_df.astype({'strike': float})
TOKEN_MAP = token_df


#filter f&o stock symbol
symbol_token = token_df[(token_df.exch_seg == 'NFO') & (token_df.instrumenttype == 'FUTSTK')]
fnoSymbol = symbol_token['name'].unique()
symbolDf = token_df[token_df.symbol.str.endswith('-EQ') & (token_df.exch_seg == 'NSE') & token_df.name.isin(fnoSymbol) & ~token_df.symbol.str.contains('TEST')].sort_values(by='symbol')
symbolDf.reset_index(inplace=True)

#get candle data
def getCandleData(token):

    try:
        historicParam={
        "exchange": "NSE",
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": f'{date.today()-timedelta(days=10)} 09:15', 
        "todate": f'{date.today()} 09:15'
        }
        return obj.getCandleData(historicParam)
    except Exception as e:
        print(f"Historic API failed: {e.message}")

def telegram_bot_sendtext(bot_message):
    max_message_length = 4096
    
    for chatID in config.BOT_CHAT_ID:
        while len(bot_message) > 0:
            chunk = bot_message[:max_message_length]
            bot_message = bot_message[max_message_length:]

            requests.post(
                f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage',
                data={'chat_id': chatID, 'text': chunk}
            )


lookBackDay = 3
start = tt.time()
highList = []
lowList = []
cnter = 0
initialMsg = "Stocks scanner started on AWS EC2"
telegram_bot_sendtext(initialMsg)

for i in symbolDf.index:
    try:
        symbol = symbolDf.loc[i]['symbol']
        token = symbolDf.loc[i]['token']
        cnter+=1
        tt.sleep(0.3)
        res = getCandleData(token)
        candleInfo = pd.DataFrame(res['data'], columns= ['data', 'open', 'high', 'low', 'close', 'vol'])
        recentCandle = candleInfo.iloc[-1]

        lastndaysCandle = candleInfo.iloc[-(lookBackDay+1):-1]
        high = lastndaysCandle.high.max()
        low = lastndaysCandle.low.min()

        if recentCandle.close > high:
            #print('High break', high, recentCandle.close, symbol)
            highList.append(symbol)
        
        elif recentCandle.close < low:
            #print('Low break', low, recentCandle.close, symbol)
            lowList.append(symbol)
    except Exception as e:
        print("Error in scan for ", symbol)

highList.append('HIGH BREAK')
high_message = '\n'.join(map(str, highList))

lowList.append('LOW BREAK')
low_message = '\n'.join(map(str, lowList))

telegram_bot_sendtext(high_message)
telegram_bot_sendtext(low_message)

print(str(cnter) + ' stocks successfully scanned')