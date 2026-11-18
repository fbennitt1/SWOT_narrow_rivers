import os
import json
import re
import sys
import time

import geopandas as gpd

import numpy as np
import pandas as pd
import xarray as xr

from datetime import date as dt_date
from datetime import datetime
from zoneinfo import ZoneInfo

from pathlib import Path
from pyproj import Transformer

def open_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        return data

def get_PIXC_files(data_dir, tiles):
    tile_set = set(str(tile) for tile in tiles) # Ensure tiles are strings
    files = []
    
    # Scan the base directory to find tile sub-directories
    with os.scandir(data_dir) as subdirs:
        for subdir in subdirs:
            # Only process if it's a directory and matches a tile in your set
            if subdir.is_dir() and subdir.name in tile_set:
                
                # Scan inside the matching tile sub-directory for files
                with os.scandir(subdir.path) as entries:
                    for entry in entries:
                        if entry.is_file(): # or entry.name.endswith('.nc') if filtering netCDF
                            files.append(entry.path)
                            
    return files


def find_SWOT_granules(mdata_dir, site_id):
    dtype_dic= {'tile': str, 'site_id': str}
    lookup = pd.read_csv(os.path.join(mdata_dir, 'usgs_gauges_swot_science_tiles.csv'),
                         dtype=dtype_dic)
    tiles = lookup[lookup['site_id'] == site_id]['tile'].to_list()
    print(tiles)

    # passes = [x[0:3] for x in tiles]

    swot_dir = '/nas/cee-ice/data/SWOT/PIXC_filtered_vD/'

    PIXC_files = get_PIXC_files(data_dir=swot_dir,
                                # passes=passes,
                                tiles=tiles)
    
    return PIXC_files

def get_metadata(pixc_file):
    # Convert to string just in case it's a Path object, and get the filename
    filename = Path(pixc_file).name
    
    # Regex searches for 8 digits, a 'T', and 6 digits (e.g., 20240315T143022)
    match = re.search(r'(\d{8}T\d{6})', filename)
    
    if not match:
        raise ValueError(f"Could not find a valid SWOT timestamp in file: {filename}")
        
    pixc_timestamp = match.group(1)
    # print(pixc_timestamp) # Debugging check
    
    pixc_dt = datetime.strptime(pixc_timestamp, "%Y%m%dT%H%M%S")
    pixc_dt = pixc_dt.replace(tzinfo=ZoneInfo('UTC'))
    
    return pixc_dt

def find_nadir(pass_num, pixel_pt):
    # Read in nadir (science orbit)
    nadir = gpd.read_parquet('/nas/cee-ice/data/SWOT/swath/swot_science_hr_2.0s_4.0s_Aug2021-v5_nadir_azimuth_3857.parquet')
    # Find candidate nadir segments
    candidates = nadir[nadir['ID_PASS'] == pass_num]
    # Find distance from each candidate to single pixel
    candidates.loc[:,'dist'] = candidates.loc[:,'geometry'].distance(pixel_pt)
    # Get nadir segment closest to single pixel
    nadir_segment = candidates[candidates.dist == candidates.dist.min()]
    # Get nadir segment azimuth
    nadir_azimuth = nadir_segment['azimuth'].item()
    print(nadir_azimuth)
    
    return nadir_azimuth

def calc_weighted_wse(df_PIXC, sigma_threshold=3.0):
    if df_PIXC.empty:
        return np.nan, np.nan
    
    # Outlier detection
    median_wse = df_PIXC['wse'].median()
    mad = (df_PIXC['wse'] - median_wse).abs().median()
    
    if mad > 0:
        z_scores = 0.6745 * (df_PIXC['wse'] - median_wse) / mad
        df_PIXC = df_PIXC[z_scores.abs() <= sigma_threshold].copy()
    
    if df_PIXC.empty:
        return np.nan, 0

    n_pixels = len(df_PIXC)
    xtrk_med = df_PIXC['cross_track'].median()
    
    # Multiply the correct columns for the weight denominator
    df_PIXC.loc[:, 'pre_denom'] = (df_PIXC['phase_noise_std']**-2
                                   * df_PIXC['dheight_dphase']**-2
                                   * df_PIXC['agg_wse'])
    
    total_denom = df_PIXC['pre_denom'].sum()
    if total_denom == 0:
        return np.nan, n_pixels
    
    df_PIXC.loc[:, 'weight'] = df_PIXC['pre_denom'] / total_denom
    df_PIXC.loc[:, 'wse_weighted'] = df_PIXC['wse'] * df_PIXC['weight']
    
    wse_weighted = df_PIXC['wse_weighted'].sum()
    return wse_weighted, n_pixels, xtrk_med

def read_PIXC_and_process(pixc_path, bounds, reach_mask):
    variables = ['cross_track', 'height', 'geoid', 
                 'solid_earth_tide', 'load_tide_fes', 'pole_tide', 
                 'phase_noise_std', 'dheight_dphase',
                 'classification', 'latitude_WGS84', 'longitude_WGS84']

    try:
        df_PIXC = pd.read_parquet(path=pixc_path, columns=variables)
    except Exception:
        return None, 0, None, None, True # Mark as corrupted

    lon_min, lat_min, lon_max, lat_max = bounds

    # Perform bounding box mask
    mask_idx = (
        (df_PIXC['longitude_WGS84'] >= lon_min) & (df_PIXC['longitude_WGS84'] <= lon_max) &
        (df_PIXC['latitude_WGS84'] >= lat_min) & (df_PIXC['latitude_WGS84'] <= lat_max)
    )
    
    df_filtered = df_PIXC[mask_idx].copy()
    del df_PIXC

    # Return now if there are no pixels in bounding box
    if df_filtered.empty:
        print("0 pixels after bounding box filter.")
        return None, 0, None, None, False

    df_filtered['wse'] = (df_filtered.height 
                          - df_filtered.geoid 
                          - df_filtered.solid_earth_tide 
                          - df_filtered.load_tide_fes 
                          - df_filtered.pole_tide)

    gdf_subset = gpd.GeoDataFrame(
        df_filtered,
        geometry=gpd.points_from_xy(df_filtered.longitude_WGS84, df_filtered.latitude_WGS84),
        crs="EPSG:4326"
    )

    gdf_subset = gpd.sjoin(gdf_subset, reach_mask[['reach_mask']], how='inner', predicate='intersects')
    print(f'{gdf_subset.shape[0]} pixels after clipping.')

    if gdf_subset.empty:
        return None, 0, None, None, False

    ### NADIR TRACK
    # Get pass number
    # Split by '/' and grab the second-to-last item: '313_234R'
    tile_folder = pixc_path.split('/')[-2]
    
    # Split by '_' and grab the first item
    pass_num = np.int32(tile_folder.split('_')[0])

    # Get single pixel for selecting correct nadir segment
    pixel_pt = gdf_subset.iloc[0].geometry      
    
    # Find azimuth of nadir track
    nadir_az = find_nadir(pass_num=pass_num, pixel_pt=pixel_pt)
    del pixel_pt
    
    wse_klass = [3.0, 4.0, 6.0, 7.0]
    gdf_subset['agg_wse'] = 0
    gdf_subset.loc[gdf_subset['classification'].isin(wse_klass), 'agg_wse'] = 1
    
    df_final = gdf_subset[gdf_subset['agg_wse'] == 1].copy()
    
    if df_final.empty:
        return None, 0, None, None, False

    wse, pixels, xtrk_med = calc_weighted_wse(df_final)
    
    return wse, pixels, xtrk_med, nadir_az, False

def year_fraction(dt):
    start = dt_date(dt.year, 1, 1).toordinal()
    year_length = dt_date(dt.year+1, 1, 1).toordinal() - start
    return round((dt.year + float(dt.toordinal() - start) / year_length), 1)

def calc_delta_h(lat):
    H_perm = -0.31460
    k_2 = 0.3
    lat_rad = np.radians(lat)
    delta_h = ((1 + k_2) * H_perm * np.sqrt(5/(4*np.pi)) * (((3/2) * np.sin(lat_rad)**2) - 0.5))
    return delta_h

def find_closest_dt(swot_row, gauge):
    diffs = (gauge['date'] - swot_row['date']).dt.total_seconds().abs()
    
    closest_idx = diffs.idxmin()
    closest_val = diffs.min()
    
    closest_row = gauge.loc[closest_idx] 
    
    stage = closest_row['stage']
    stage_dt = closest_row.date
    
    return stage, stage_dt, closest_val

def to_swot_crs(df):
    df = df.copy()
    
    # Pre-define columns to avoid "SettingWithCopy" warnings
    df['lon_wgs84'] = 0.0
    df['lat_wgs84'] = 0.0
    df['datum_offset_m'] = 0.0

    groups = df.groupby('epoch_01yr')
    total_groups = len(groups)
    
    print(f"Starting pyproj pipeline for {len(df)} points...")

    for i, (epoch_yr, group) in enumerate(groups, 1):
        epoch_val = float(epoch_yr)
        print(f"[{i}/{total_groups}] Epoch {epoch_val}: {len(group)} points", end="\r")

        # Create a manual pipeline string
        # This bypasses the keyword arguments and talks directly to the PROJ engine
        pipeline = (
            f"+proj=pipeline "
            f"+step +inv +init=EPSG:6349 "
            f"+step +proj=unitconvert +xy_in=rad +z_in=m +xy_out=deg +z_out=m "
            f"+step +proj=cart +ellps=GRS80 "
            f"+step +proj=helmert +convention=coordinate_frame "
            f"+x=0.99343 +y=-1.90331 +z=-0.51255 +rx=1.25818e-07 +ry=4.67384e-08 +rz=5.21262e-08 +s=0 "
            f"+dx=0.00079 +dy=-0.0006 +dz=-0.00134 +drx=3.248e-10 +dry=5.818e-10 +drz=5.236e-10 +ds=0 "
            f"+t_epoch={epoch_val} +s_epoch=2010.0 "
            f"+step +inv +proj=cart +ellps=WGS84 "
            f"+step +init=EPSG:9057+3855"
        )
        
        # Or, simpler: if your environment supports f-strings and basic init
        # We use from_pipeline to handle the epochs manually
        pipe = (
            f"+proj=pipeline "
            f"+step +init=EPSG:6349 "
            f"+step +proj=set +t={epoch_val} "
            f"+step +inv +init=EPSG:6349 "
            f"+step +init=EPSG:9057+3855"
        )

        # Recommendation: Use the "Area of Interest" approach if Pipeline is too complex
        # If your version is just slightly old, you can use from_crs and then
        # set the epoch on the coordinates themselves (proj 7+)
        
        transformer = Transformer.from_crs("EPSG:6349", "EPSG:9057+EPSG:3855", always_xy=True)

        # In pyproj < 3.4, we pass the time (epoch) as a 4th coordinate (x, y, z, t)
        # Create an array of the same length as the group for the epoch
        epochs = [epoch_val] * len(group)
        
        new_lon, new_lat, alt_out, _ = transformer.transform(
            group['dec_long_va'].values,
            group['dec_lat_va'].values,
            group['alt_va'].values,
            epochs
        )

        df.loc[group.index, 'lon_wgs84'] = new_lon
        df.loc[group.index, 'lat_wgs84'] = new_lat
        df.loc[group.index, 'datum_offset_m'] = alt_out - group['alt_va'].values

    print(f"\nDone.")
    return df


def process_PIXC(index, save_dir):
    print(f"DEBUG: Task {index} started", flush=True)
    
    mdata_dir = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
    data_dir = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/'
    gauge_dir = '/nas/cee-water/cjgleason/fiona/USGS_gauges/sites_2026/'
    
    # Check if JSON load is the hang
    try:
        site_ids = open_json(os.path.join(mdata_dir, 'usgs_gauges_cleaned_20251206.json'))
        site_id = site_ids[index]
        print(f'USGS site: {site_id}', flush=True)
    except Exception as e:
        print(f"FAIL at JSON load: {e}", flush=True)
        return

    # Check if file already exists--if so, skip
    os.makedirs(save_dir, exist_ok=True)
    save_file = os.path.join(save_dir, f'site_{site_id}.parquet')
    if os.path.isfile(save_file):
        print(f'Site {site_id} already processed, skipping')
        return

    # Check for gauge file
    gauge_path = os.path.join(gauge_dir, f'{site_id}.parquet')
    if not os.path.exists(gauge_path):
        print(f"Message: {site_id} not found in {gauge_dir}")
        return 

    # Check if Parquet Metadata read is the hang
    print(f"DEBUG: Attempting to read mask for {site_id}", flush=True)
    mask = gpd.read_parquet(
        os.path.join(data_dir, 'nhd_reach_masks_for_gauges_combined.parquet'),
        filters=[('site_id', '==', site_id)]
    )
    
    if mask.empty:
        print(f"No mask found for {site_id}", flush=True)
        return
        
    print(f"DEBUG: Mask loaded for {site_id}. Width: {mask['WidthM'].iloc[0]}", flush=True)

    # Extract needed values from the mask you already have
    nhd_id = mask['NHDPlusID'].iloc[0]
    widthM = mask['WidthM'].iloc[0]
    new_width = mask['new_width'].iloc[0]
    huc2 = mask['huc2'].iloc[0]
    huc4 = mask['huc4'].iloc[0]

    print('Extracted gauge metadata.')
    
    # Get bounds and reach_mask geometry for the PIXC clipper
    reach_mask = mask.to_crs('EPSG:4326')
    buffered_mask = mask.to_crs('EPSG:3857').buffer(50, cap_style='flat').to_crs('EPSG:4326')
    bounds = buffered_mask.total_bounds
    print(f"Width: {widthM}")

    # Process PIXC Files
    print('Starting to process SWOT:')
    pixc_files = find_SWOT_granules(mdata_dir, site_id)
    records = {}
    corrupted_files = []
    
    for pixc_file in pixc_files:
        # print(pixc_file)
        # sys.exit()
        pixc_dt = get_metadata(pixc_file=pixc_file)
        wse_swot, n_pixel, xtrk_med, nadir_az, is_corrupted = read_PIXC_and_process(
            pixc_path=pixc_file, bounds=bounds, reach_mask=reach_mask
        )
        
        if is_corrupted:
            corrupted_files.append(pixc_file)
            continue
            
        records[pixc_dt] = {'wse_swot': wse_swot, 'n_pixels': n_pixel, 'xtrk_med': xtrk_med, 'nadir_az': nadir_az}
    
    print(f"Total corrupted files found: {len(corrupted_files)}")
    if not records:
        print('No SWOT data found after masking.')
        return

    # 4. Gauge Processing
    gauge = pd.read_parquet(gauge_path)
    if gauge.empty: return

    print('Gauges read in.')
    
    if str(gauge.index.tz) != 'UTC':
        gauge = gauge.tz_convert('UTC')
    
    gauge = gauge.reset_index().rename(columns={'datetime': 'date'})
    gauge = gauge[gauge['stage'] != -999999.00]
    gauge['stage'] = gauge['stage'] * 0.3048 # Convert to meters

    # Match SWOT to Gauge
    df = pd.DataFrame.from_dict(records, orient='index').reset_index().rename(columns={'index': 'date'})
    df = df[df['date'].between(gauge['date'].min(), gauge['date'].max())]
    if df.empty: return
        
    # Closest DT matching
    df['epoch_01yr'] = df.date.apply(year_fraction)
    stage, stage_dt, delta_t = zip(*df.apply(find_closest_dt, args=(gauge,), axis=1))
    df['stage'], df['gauge_date'], df['delta_t'] = stage, stage_dt, delta_t
    df = df[df['delta_t'] < 3600]

    if df.empty: return
    print('Finished date-time matching.')

    # 5. Final Station Metadata (Use filters to avoid loading the whole file!)
    nhd_gauges = pd.read_parquet(
        f'{gauge_dir}/../usgs_stations_with_stage_and_nhd_metadata.parquet',
        filters=[('site_id', '==', site_id)],
        columns=['site_id', 'dec_lat_va', 'dec_long_va','alt_va']
    )
    print('Read in gauge metadata.')
    
    df['site_id'] = site_id
    df['dec_lat_va'] = nhd_gauges['dec_lat_va'].values[0]
    df['dec_long_va'] = nhd_gauges['dec_long_va'].values[0]
    df['alt_va'] = nhd_gauges['alt_va'].values[0] * 0.3048
    
    delta_h = calc_delta_h(df['dec_lat_va'].iloc[0])
    print(f'Started gauge datum change at: {time.time()}')
    df = to_swot_crs(df)
    print(f'Finished gauge datum change: {time.time()}')
    
    df['wse_gauge'] = df['stage'] + df['alt_va'] + df['datum_offset_m'] + delta_h

    # Attach reach metadata and save
    df[['NHDPlusID', 'WidthM', 'new_width', 'huc2', 'huc4']] = [nhd_id, widthM, new_width, huc2, huc4]
    
    os.makedirs(save_dir, exist_ok=True)
    df.to_parquet(os.path.join(save_dir, f'site_{site_id}.parquet'))
    print('Completed, wrote out!')

if __name__ == "__main__":
    task = int(os.environ['SLURM_ARRAY_TASK_ID'])
    date = '2026_06_01'
    save_dir = f'/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_output/PIXC_vD_wse_{date}_rel_abs/'
    
    process_PIXC(index=task, save_dir=save_dir)