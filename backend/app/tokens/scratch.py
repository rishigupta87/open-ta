import pandas as pd
import requests
import os
from datetime import datetime, timedelta

# URL to retrieve the JSON data
url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'

# Retrieve the data from the URL
response = requests.get(url)
data = response.json()

# Convert JSON data to DataFrame
df = pd.DataFrame(data)

# Filter for all traded options and futures data (NFO, FUTSTK, OPTSTK, FUTIDX, OPTIDX)
filtered_df = df[(df['exch_seg'] == 'NFO') & (df['instrumenttype'].isin(['FUTSTK', 'OPTSTK', 'FUTIDX', 'OPTIDX']))]

# Remove all records where the 'name' column contains 'test' (case insensitive)
filtered_df = filtered_df[~filtered_df['name'].str.contains('test', case=False, na=False)]

# Function to extract expiry date from the name if not present in the expiry field
def extract_expiry(row):
    if pd.isna(row['expiry']) or row['expiry'] == '':
        try:
            # Extract date from name
            expiry_str = row['name'][-7:]  # Assuming the date is always at the end of the name
            return pd.to_datetime(expiry_str, format='%d%b%y', errors='coerce')
        except:
            return pd.NaT
    else:
        return pd.to_datetime(row['expiry'], errors='coerce')

# Apply the function to the DataFrame
filtered_df['expiry'] = filtered_df.apply(extract_expiry, axis=1)

# Ensure expiry is in datetime format
filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'], errors='coerce')

# Get the current date
now = datetime.now()

# Define function to get nearest expiry dates for options and futures
def get_nearest_expiries(group, instrumenttype):
    if 'FUT' in instrumenttype:
        # Get the nearest two expiries for futures
        nearest_expiries = group['expiry'].nsmallest(2)
    else:
        # Get the nearest expiry for options
        nearest_expiries = group['expiry'].nsmallest(1)
    return group[group['expiry'].isin(nearest_expiries)]

# Group by 'name' and 'instrumenttype' and apply the function
filtered_df = filtered_df.groupby(['name', 'instrumenttype']).apply(
    lambda x: get_nearest_expiries(x, x['instrumenttype'].iloc[0])
).reset_index(drop=True)

# Extract the strike price from 'symbol' and rename the column
def extract_strike_price(row):
    if row['instrumenttype'] in ['OPTSTK', 'OPTIDX']:
        parts = row['symbol'].split(row['expiry'].strftime('%d%b%y').upper())
        if len(parts) > 1:
            return parts[1]
        else:
            return row['symbol']
    else:
        return row['symbol']  # For FUTSTK and FUTIDX, retain the symbol

# Apply the strike price extraction function
filtered_df['call_put'] = filtered_df.apply(extract_strike_price, axis=1)

# Remove the date parts from the extracted strike price for options
def clean_strike_price(sp):
    return ''.join([i for i in sp if not i.isdigit()])

filtered_df['call_put'] = filtered_df['call_put'].apply(clean_strike_price)

# Convert 'strike' column to numeric type
filtered_df['strike'] = pd.to_numeric(filtered_df['strike'], errors='coerce')

# Adjust the 'strike' column by dividing by 100 and formatting to 2 decimal places
filtered_df['strike'] = (filtered_df['strike'] / 100).round(2)

# Separate the data into index and stock data
index_df = filtered_df[filtered_df['instrumenttype'].isin(['FUTIDX', 'OPTIDX'])]
stock_df = filtered_df[filtered_df['instrumenttype'].isin(['FUTSTK', 'OPTSTK'])]

# Get the current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))

# Define the output file paths in the script's directory
index_file_path = os.path.join(script_dir, 'index_instruments.csv')
stock_file_path = os.path.join(script_dir, 'stock_instruments.csv')

# Drop the 'symbol' column
index_df = index_df.drop(columns=['symbol'])
stock_df = stock_df.drop(columns=['symbol'])

# Save the index and stock data to separate CSV files
index_df.to_csv(index_file_path, index=False)
stock_df.to_csv(stock_file_path, index=False)

print("Index Instruments DataFrame:")
print(index_df[['token', 'name', 'expiry', 'strike', 'lotsize', 'instrumenttype', 'exch_seg', 'tick_size', 'call_put']])
print("Stock Instruments DataFrame:")
print(stock_df[['token', 'name', 'expiry', 'strike', 'lotsize', 'instrumenttype', 'exch_seg', 'tick_size', 'call_put']])
