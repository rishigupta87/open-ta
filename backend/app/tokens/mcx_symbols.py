import pandas as pd
import requests
import os
from datetime import datetime

# URL to retrieve the JSON data
url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'

def fetch_data(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def preprocess_data(data, specific_names):
    df = pd.DataFrame(data)
    # Filter only for the specific names and exchange segment
    filtered_df = df[(df['exch_seg'] == 'MCX') & (df['name'].isin(specific_names)) & (df['instrumenttype'].isin(['FUTCOM', 'OPTFUT']))]
    # Remove test records
    filtered_df = filtered_df[~filtered_df['name'].str.contains('test', case=False, na=False)]
    return filtered_df

def extract_expiry(row):
    if pd.isna(row['expiry']) or row['expiry'] == '':
        try:
            # Extract date from symbol
            if row['instrumenttype'] == 'FUTCOM':
                expiry_str = row['symbol'][len(row['name']):len(row['name']) + 5]  # Extract date part from symbol
            else:
                expiry_str = row['symbol'][len(row['name']):len(row['name']) + 5]  # Extract date part from symbol
            return pd.to_datetime(expiry_str, format='%d%b', errors='coerce').replace(year=datetime.now().year)
        except:
            return pd.NaT
    else:
        return pd.to_datetime(row['expiry'], errors='coerce')

def get_nearest_expiries(group, instrumenttype):
    if instrumenttype == 'FUTCOM':
        nearest_expiries = group['expiry'].nsmallest(2)
    else:
        nearest_expiry = group['expiry'].nsmallest(1)
        nearest_expiries = nearest_expiry if not nearest_expiry.empty else pd.Series([pd.NaT])
    return group[group['expiry'].isin(nearest_expiries)]

def extract_strike_and_call_put(row):
    if row['instrumenttype'] == 'OPTFUT':
        parts = row['symbol'][len(row['name']) + 5:]  # Extracting the part after the expiry
        strike_part = ''.join([c for c in parts if c.isdigit() or c == '.'])
        call_put = parts.replace(strike_part, '')
        return float(strike_part) if strike_part else 0.0, call_put
    else:
        return 0.0, row['symbol']

def process_instruments(filtered_df):
    futures_df = filtered_df[filtered_df['instrumenttype'] == 'FUTCOM'].copy()
    options_df = filtered_df[filtered_df['instrumenttype'] == 'OPTFUT'].copy()

    futures_df['expiry'] = futures_df.apply(extract_expiry, axis=1)
    futures_df['expiry'] = pd.to_datetime(futures_df['expiry'], errors='coerce')
    futures_df = futures_df.groupby(['name', 'instrumenttype'], group_keys=False).apply(lambda x: get_nearest_expiries(x, 'FUTCOM')).reset_index(drop=True)

    options_df['expiry'] = options_df.apply(extract_expiry, axis=1)
    options_df['expiry'] = pd.to_datetime(options_df['expiry'], errors='coerce')
    options_df = options_df.groupby(['name', 'instrumenttype'], group_keys=False).apply(lambda x: get_nearest_expiries(x, 'OPTFUT')).reset_index(drop=True)

    options_df['strike'], options_df['call_put'] = zip(*options_df.apply(extract_strike_and_call_put, axis=1))

    futures_df['strike'], futures_df['call_put'] = 0.0, futures_df['symbol']  # For FUTCOM, retain the symbol

    final_df = pd.concat([futures_df, options_df])
    return final_df

def main():
    specific_names = ['CRUDEOIL', 'NATURALGAS']
    data = fetch_data(url)
    filtered_df = preprocess_data(data, specific_names)

    final_df = process_instruments(filtered_df)

    # Get the current script directory
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Define the output file path in the script's directory
    output_file_path = os.path.join(script_dir, 'commodities_instruments.csv')

    # Save the data to a CSV file
    final_df.to_csv(output_file_path, index=False)

    print("Commodities DataFrame:")
    print(final_df[['token', 'symbol', 'name', 'expiry', 'strike', 'lotsize', 'instrumenttype', 'exch_seg', 'tick_size', 'call_put']])

if __name__ == "__main__":
    main()
