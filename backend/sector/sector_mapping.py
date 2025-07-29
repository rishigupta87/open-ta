import os
import glob
import pandas as pd

SECTOR_DIR = "/app/sector/"

def load_symbol_to_sector():
    mapping = {}
    sector_files = glob.glob(os.path.join(SECTOR_DIR, "ind_nifty*list.csv"))
    for path in sector_files:
        basename = os.path.basename(path)
        # Extract sector (between 'nifty' and 'list')
        sector = basename.split("nifty")[1].replace("list.csv", "").upper()
        df = pd.read_csv(path)
        for symbol in df["Symbol"]:
            mapping[symbol.strip().upper()] = sector
    return mapping
