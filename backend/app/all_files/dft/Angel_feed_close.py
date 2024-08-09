#!/usr/bin/env python
# coding: utf-8

# In[ ]:


pip show smartapi-python


# In[ ]:


apikey = 'your_apikey'
username = 'your_username'
pwd = 'your_password'


# In[ ]:


from smartapi import SmartConnect
from smartapi import SmartWebSocket
import threading
from datetime import date
import requests
import pandas as pd
import time

obj=SmartConnect(api_key=apikey)
data = obj.generateSession(username,pwd)
refreshToken= data['data']['refreshToken']
feedToken=obj.getfeedToken()
feedToken


# In[ ]:


def feed():
    token="mcx_fo|228225"   
    task="mw"   # mw|sfi|dp

    def on_message(ws, message):
        print("Ticks: {}".format(message))
        

    def on_open(ws):
        print("on open")
        ss.subscribe(task,token)

    def on_error(ws, error):
        print(error)

    def on_close(ws):
        print("Close")

    # Assign the callbacks.
    ss._on_open = on_open
    ss._on_message = on_message
    ss._on_error = on_error
    ss._on_close = on_close

    ss.connect()


# In[ ]:


from smartapi import SmartWebSocket
import threading

ss = SmartWebSocket(feedToken, username)
threading.Thread(target = feed).start()


# In[ ]:


url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
d = requests.get(url).json()

token_df = pd.DataFrame.from_dict(d)
token_df['expiry'] = pd.to_datetime(token_df['expiry']).apply(lambda x: x.date())
token_df = token_df.astype({'strike': float})
token_df[(token_df['instrumenttype'] == 'FUTCOM') & (token_df.exch_seg == 'MCX') ]


# In[ ]:


ss.ws.close()

