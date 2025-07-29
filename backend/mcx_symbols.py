import pandas as pd
import requests
from datetime import datetime
import os

# URL to retrieve the JSON data
MCX_URL = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'

def fetch_mcx_data(url=MCX_URL):
    """Fetch JSON data from AngelBroking"""
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def preprocess_data(data, specific_names):
    df = pd.DataFrame(data)
    # Filter MCX + specific commodities (CRUDEOIL, NATURALGAS)
    df = df[
        (df['exch_seg'] == 'MCX') &
        (df['name'].isin(specific_names)) &
        (df['instrumenttype'].isin(['FUTCOM', 'OPTFUT']))
    ]
    df = df[~df['name'].str.contains('test', case=False, na=False)]
    return df

def extract_expiry(row):
    if pd.isna(row['expiry']) or row['expiry'] == '':
        try:
            expiry_str = row['symbol'][len(row['name']):len(row['name']) + 5]
            return pd.to_datetime(expiry_str, format='%d%b', errors='coerce').replace(year=datetime.now().year)
        except:
            return pd.NaT
    else:
        return pd.to_datetime(row['expiry'], errors='coerce')

def get_nearest_expiries(group, instrumenttype):
    # FUTCOM → 2 nearest expiries, OPTFUT → 1 nearest expiry
    nearest_expiries = group['expiry'].nsmallest(2 if instrumenttype == 'FUTCOM' else 1)
    if nearest_expiries.empty:
        return pd.DataFrame()
    return group[group['expiry'].isin(nearest_expiries)]

def extract_strike_and_call_put(row):
    if row['instrumenttype'] == 'OPTFUT':
        name_len = len(row['name'])
        
        # Skip name + expiry (7 chars for DDMMMYY)
        parts = row['symbol'][name_len + 7:]
        
        # Extract strike (digits) and call/put (remaining text)
        strike_part = ''.join([c for c in parts if c.isdigit() or c == '.'])
        call_put = parts.replace(strike_part, '')  # CE or PE
        
        return float(strike_part) if strike_part else 0.0, call_put
    else:
        return 0.0, row['symbol']


def process_mcx_instruments(filtered_df):
    futures_df = filtered_df[filtered_df['instrumenttype'] == 'FUTCOM'].copy()
    options_df = filtered_df[filtered_df['instrumenttype'] == 'OPTFUT'].copy()

    # Expiry parsing
    futures_df['expiry'] = futures_df.apply(extract_expiry, axis=1)
    options_df['expiry'] = options_df.apply(extract_expiry, axis=1)

    # Filter nearest expiries
    futures_df = futures_df.groupby(['name', 'instrumenttype'], group_keys=False).apply(lambda g: get_nearest_expiries(g, 'FUTCOM'))
    options_df = options_df.groupby(['name', 'instrumenttype'], group_keys=False).apply(lambda g: get_nearest_expiries(g, 'OPTFUT'))

    # Strike + Call/Put for options
    if not options_df.empty:
        options_df['strike'], options_df['call_put'] = zip(*options_df.apply(extract_strike_and_call_put, axis=1))

    # FUTCOM → no strike
    futures_df['strike'], futures_df['call_put'] = 0.0, futures_df['symbol']

    return pd.concat([futures_df, options_df]).reset_index(drop=True)

def fetch_and_process_commodities(commodities=None):
    if commodities is None:
        commodities = ['CRUDEOIL', 'NATURALGAS']
    
    data = fetch_mcx_data()
    filtered_df = preprocess_data(data, commodities)
    return process_mcx_instruments(filtered_df)



def save_tokens_to_csv(df):
    #Save inside websocket-bridge folder
    shared_path = "/websocket-bridge/commodities_instruments.csv"
    df.to_csv(shared_path, index=False)
    return shared_path