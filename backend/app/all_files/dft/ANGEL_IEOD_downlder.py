#!/usr/bin/env python
# coding: utf-8

# In[2]:


apikey = 'api_key'
username = 'username'
pwd = 'password'


# In[3]:


from smartapi import SmartConnect
import time as tt
import requests
import pandas as pd
pd.set_option('max_columns', None)
from datetime import datetime,date,time 

obj=SmartConnect(api_key=apikey)
data = obj.generateSession(username,pwd)
#print(data)
refreshToken= data['data']['refreshToken']
res = obj.getProfile(refreshToken)
res['data']['exchanges'] 


# In[4]:


url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
d = requests.get(url).json()
token_df = pd.DataFrame.from_dict(d)
token_df['expiry'] = pd.to_datetime(token_df['expiry']).apply(lambda x: x.date())
token_df = token_df.astype({'strike': float})

#token_df = token_df[(token_df['name'] == 'BANKNIFTY') & (token_df['instrumenttype'] == 'OPTIDX') ]
token_df


# In[5]:


symbol_token = token_df[(token_df.exch_seg =='NFO') & (token_df.instrumenttype =='FUTSTK')]
fnoSymbol = symbol_token.name.unique()
eqSymbolDf = token_df[token_df.symbol.str.endswith('-EQ') & (token_df.exch_seg =='NSE') & token_df.name.isin(fnoSymbol)].sort_values(by ='symbol') 
eqSymbolDf.reset_index(inplace =True)
eqSymbolDf


# In[6]:


currentExpiry = symbol_token.expiry.unique().tolist()
currentExpiry.sort()
recentExpiry = currentExpiry[0]
recentExpiry


# In[7]:


futSymbolDf = symbol_token[symbol_token.expiry == recentExpiry]
futSymbolDf.reset_index(drop=True,inplace= True)
futSymbolDf


# In[8]:


def getCandleData(symbolInfo):
   
    try:
        historicParam={
        "exchange": symbolInfo.exch_seg,
        "symboltoken": symbolInfo.token,
        "interval": "ONE_MINUTE",
        "fromdate": f'{date.today()} 09:15' , 
        "todate": f'{date.today()} 15:30' 
        }
        res_json=  obj.getCandleData(historicParam)
        columns = ['timestamp','open','high','low','close','volume']
        df = pd.DataFrame(res_json['data'], columns=columns)
        df['timestamp'] = pd.to_datetime(df['timestamp'],format = '%Y-%m-%dT%H:%M:%S')
        df['symbol'] = symbolInfo.symbol
        df['expiry'] = symbolInfo.expiry
        print(f"Done for {symbolInfo.symbol}")
        tt.sleep(0.2)
        return df
    except Exception as e:
        print(f"Historic Api failed: {e} {symbolInfo.symbol}")


# In[9]:


eqdfList = []
for i in eqSymbolDf.index :
    try:
        symbol = eqSymbolDf.loc[i]
        candelRes = getCandleData(symbol)
        eqdfList.append(candelRes)
    except Exception as e:
        print(f"Fetching Hist Data  failed {symbol.symbol} : {e}")
   


# In[11]:


eQFinalDf = pd.concat(eqdfList, ignore_index = True)
eQFinalDf


# In[12]:


eQFinalDf.to_csv(f'ieod/{date.today()}_EQ.csv')


# In[13]:


futdfList = []
for i in futSymbolDf.index :
    try:
        symbol = futSymbolDf.loc[i]
        candelRes = getCandleData(symbol)
        futdfList.append(candelRes)
    except Exception as e:
        print(f"Fetching Fut Hist Data  failed {symbol.symbol} : {e}")


# In[14]:


futFinalDf = pd.concat(futdfList, ignore_index = True)
futFinalDf


# In[15]:


futFinalDf.to_csv(f'ieod/{date.today()}_FUT.csv')

