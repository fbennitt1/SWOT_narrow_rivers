import os
import json
from pathlib import Path
import signal

import geopandas as gpd
import pandas as pd
import dataretrieval.nwis as nwis

from tqdm.auto import tqdm

def open_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        return data

# Constants
DATASETS = Path('/nas/cee-water/cjgleason/fiona')
DATA_DIR = DATASETS / 'USGS_gauges'
SAVE_DIR = DATA_DIR / 'sites_2026'
SAVE_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = '2023-07-26'
END_DATE = '2026-03-23'

def open_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Read in good sites
mdata_dir = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
site_ids = open_json(os.path.join(mdata_dir, 'usgs_gauges_cleaned_20251206.json'))


data_dir = '/nas/cee-water/cjgleason/fiona/USGS_gauges/sites_2026/'
filenames = [os.path.splitext(f)[0] for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

remaining = list(set(site_ids) - set(filenames))

# # Subset to sites of interest
# nhd_sites = nhd_sites[nhd_sites['site_id'].isin(site_ids)]
# nhd_sites_subset = nhd_sites.iloc[1770:]

missing_sites = []

# Define what happens when the "alarm" goes off
def handler(signum, frame):
    raise TimeoutError("NWIS call took too long!")

# Register the signal
signal.signal(signal.SIGALRM, handler)

missing_sites = []

for site_id in tqdm(remaining):
    filename = SAVE_DIR / f"{site_id}.parquet"
    if filename.exists(): continue
    
    # Set the alarm for 30 seconds
    signal.alarm(30) 
    
    try:
        data, _ = nwis.get_iv(sites=site_id, start=START_DATE, end=END_DATE, parameterCd='00065')
        
        # Turn off the alarm if it finished in time
        signal.alarm(0) 

        if not data.empty and '00065' in data.columns:
            data = data.rename(columns={'00065': 'stage', '00065_cd': 'quality_flag'})
            data = data.drop(columns='site_no', errors='ignore')
            data.to_parquet(filename)
        else:
            missing_sites.append(site_id)
            
    except (TimeoutError, Exception) as e:
        signal.alarm(0) # Always reset the alarm on error
        print(f"Skipping {site_id} due to {type(e).__name__}")
        missing_sites.append(site_id)

print(f"Download complete. {len(missing_sites)} sites had no data.")