##################################################
## Authors: Merritt Harlan (USGS), Alexander Hernes (USGS)
## Email: mharlan@usgs.gov, ahernes@usgs.gov
## Updated by: Fiona Bennitt (UMass Amherst), fbennitt@umass.edu
## Last updated March 2026
#----
## Encoding: utf-8
## Python version: 3.10.12
## See requirements.txt for package dependencies
#----
## Usage: $ python SWOT_lakes_export_data.py --data-root <output_directory | optional> --geojson-path <path_to_geojson_file | optional>
#-------------------------------------------------
# DESCRIPTION: This script runs through previously-downloaded SWOT PIXC data and discards land pixels and those outside the
# acceptable cross-track distance (10 km to 50 km is acceptable). It also applies a filter flag to "degraded" and "bad" data.
# Final data is saved as one parquet file per granule.
#-------------------------------------------------
# DISCLAIMER: This software is preliminary or provisional and is subject to revision. 
# It is being provided to meet the need for timely best science. The software has not received final approval 
# by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government 
# as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. 
# The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any 
# damages resulting from the authorized or unauthorized use of the software. This software is provided 'AS IS'
##################################################

import argparse
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
#from itertools import islice
import json
#import earthaccess
import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
#from shapely.geometry import MultiPolygon, Point
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

def getFiles(data_dir):
    files = []
    for file in os.listdir(data_dir):
        if not file.startswith('.'):
            files.append(os.path.join(data_dir, file))
    return files


# def batch_iter(iterable, size):
#     """Return batches of input iterable of given size.

#     Args:
#         iterable (list): Iterable to be batched.
#         size (int): Desired batch size.

#     Yields:
#         list: Batch of length = size
#     """
#     it = iter(iterable)
#     while batch := list(islice(it, size)):
#         yield batch

def flatten_dict(d, parent_key='', sep='_'):
    """
    Flatten a nested dictionary of rows/data points into a single dictionary.
    """
    items = []
    
    if isinstance(d, dict):  # Only flatten dictionaries
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                # Recursively flatten nested dictionaries
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list) or isinstance(v, np.ndarray):
                # Flatten lists or arrays into separate columns
                for i, elem in enumerate(v):
                    items.append((f"{new_key}_{i}", elem))
            else:
                # Add simple key-value pairs
                items.append((new_key, v))
    return dict(items)


def safe_rmtree(path, max_attempts=5):
    """Safely remove a directory and its contents, retrying on Windows PermissionError."""
    for attempt in range(max_attempts):
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(1)  # wait a second and retry
    print(f"Warning: Could not remove directory {path} after {max_attempts} attempts")

# Retry decorator with exponential backoff
@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(5))
def open_pixc_file(pixc_file):
    """
    Open the SWOT pixel netcdf file, retrying on failure.
    
    Args:
        pixc_file (str): SWOT pixel netcdf file.
        
    Returns:
        result: Opened h5py file object.
    """
    return h5py.File(pixc_file, 'r')

def filter_pixc_file(pixc_file,
                     # input_lake,
                     # start_date, end_date,
                     kwargs):
    """
    Process an SWOT pixel netcdf file, crop data to a bounding box, apply filtering criteria, and return the filtered data.
    Args:
        pixc_file (h5py.File or str): Path to the SWOT pixel netcdf file
        # input_lake: (GeoDataFrame): GeoDataFrame containing 'sw_lon', 'sw_lat', 'ne_lon', 'ne_lat' and elevation bounds (elev_min, elev_max)
        start_date (str, optional): Start date for filtering.
        end_date (str, optional): End date for filtering. 
        **kwargs: Additional arguments for filtering criteria.

    Returns:
        dict: A dictionary of filtered data for relevant attributes.
    """
    # Unpack kwargs
    classification_vals = kwargs.get('classification_vals')
    # water_classification = kwargs.get('water_classification')
    bitwise_qual_max = kwargs.get('bitwise_qual_max')
    geolocation_qual_th = kwargs.get('geolocation_qual_th')
    sig0_qual_th = kwargs.get('sig0_qual_th')
    interferogram_qual_th = kwargs.get('interferogram_qual_th')
    classification_qual_th = kwargs.get('classification_qual_th')    
    
    # Extract date from the file URL
    #url = pixc_file.full_name
    # Split after the last '/' to get the file name
    base_url = "https://archive.swot.podaac.earthdata.nasa.gov/podaac-swot-ops-cumulus-protected/SWOT_L2_HR_PIXC_D/"
    url = pixc_file.split('/')[-1]
    file_name = url.split('\\')[-1]
    full_url = f"{base_url}{file_name}"
    
    date_match = re.search(r'(\d{8}T\d{6})', url)
    date_str = pd.to_datetime(date_match.group(1), format="%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S") if date_match else "unknown"

    crid_match = re.search(r'(\w{4})(?=_\d{2}\.nc$)', url)
    crid_str = crid_match.group(1) if crid_match else "unknown"

    try:
        
        with open_pixc_file(pixc_file) as f:
            
            num_azimuth_looks = f['pixel_cloud'].attrs['num_azimuth_looks']
            group = f['pixel_cloud']

            # Define required variables
            var_names = [
                'azimuth_index', 'range_index',
                'water_frac', 'water_frac_uncert', 'classification',
                'false_detection_rate', 'missed_detection_rate',
                'bright_land_flag', 'prior_water_prob',
                'eff_num_rare_looks', 'eff_num_medium_looks',
                'height', 'cross_track', 'pixel_area', 'inc',
                'phase_noise_std', 'dlatitude_dphase',
                'dlongitude_dphase','dheight_dphase',
                'eff_num_medium_looks', 'sig0', 'sig0_uncert',
                'height_cor_xover',
                'geoid', 'solid_earth_tide', 'load_tide_fes',
                'load_tide_got', 'pole_tide',
                'ancillary_surface_classification_flag',
                'interferogram_qual', 'classification_qual',
                'geolocation_qual', 'sig0_qual'
            ]

            # Load full spatial data
            cropped_data = {
                'latitudes': group['latitude'][:],
                'longitudes': group['longitude'][:]
            }

            # Helper function without mask
            def read_variable(group, var_name):
                return group[var_name][:]
            
            with ThreadPoolExecutor(max_workers=min(24, len(var_names))) as executor:
                # Submit jobs for full arrays
                future_to_var = {executor.submit(read_variable, group, var): var for var in var_names}
                
                for future in as_completed(future_to_var):
                    var = future_to_var[future]
                    try:
                        cropped_data[var] = future.result()
                    except Exception as exc:
                        print(f'Error loading {var}: {exc}')
            

            # Apply classification, geolocation, and elevation filters
            filter_mask = (
                np.isin(cropped_data['classification'], classification_vals) &
                (np.abs(cropped_data['cross_track']) >= 10000) &
                (np.abs(cropped_data['cross_track']) <= 60000)
            )

            # Apply filtering mask to all relevant arrays
            filtered_data = {
                key: np.compress(filter_mask, val) if isinstance(val, np.ndarray) else val
                for key, val in cropped_data.items()
            }

            # Add "filtered" attribute based on additional criteria
            quality_mask = (
                # np.isin(filtered_data['classification'], water_classification) &
                (filtered_data['geolocation_qual'] >= geolocation_qual_th) &
                (filtered_data['sig0_qual'] >= sig0_qual_th) &
                (filtered_data['interferogram_qual'] >= interferogram_qual_th) &
                (filtered_data['classification_qual'] >= classification_qual_th)
            )

            # Prepare the final data table (flatten each point as a row in the table)
            rows = []
            num_pixels = len(filtered_data['latitudes'])

            for i in range(num_pixels):
                row = {
                    'datetime_UTC': date_str,
                    'pixc_url': full_url,
                    'pixc_crid': crid_str,
                    'num_azimuth_looks': num_azimuth_looks,
                    'bitwise_qual_max': bitwise_qual_max,
                    # 'water_classification': ';'.join(map(str, water_classification)),
                    'latitude_WGS84': filtered_data['latitudes'][i],
                    'longitude_WGS84': filtered_data['longitudes'][i],
                    'quality_issue': int(quality_mask[i]) # 0 means passes filter, 1 means quality issue
                }

                for var in var_names:
                    row[var] = filtered_data[var][i]

                rows.append(row)

            return rows
            
    except Exception as e:
        print(f"Error processing {pixc_file}: {e}")
        return [{"url": url, "date": date_str, "error": str(e)}]

# # 1. Calculate the final quality mask
# quality_mask = (
#     np.isin(filtered_data['classification'], water_classification) &
#     (filtered_data['geolocation_qual'] <= geolocation_qual_th) &
#     (filtered_data['sig0_qual'] <= sig0_qual_th) &
#     (filtered_data['interferogram_qual'] <= interferogram_qual_th) &
#     (filtered_data['classification_qual'] <= classification_qual_th)
# )

# # 2. Apply this mask to all arrays in filtered_data BEFORE the loop
# for key in filtered_data:
#     if isinstance(filtered_data[key], np.ndarray) and len(filtered_data[key]) == num_pixels:
#         filtered_data[key] = filtered_data[key][quality_mask]

# # 3. Update the pixel count for the loop
# num_pixels = len(filtered_data['latitudes'])

# # Now the loop only processes pixels that passed the quality thresholds
# for i in range(num_pixels):
#     row = {
#         'datetime_UTC': date_str,
#         # ... rest of your row logic ...


def main(files, output_dir, kwargs=None, pixel_names=None):
    """
    Processes only lakes specified in selected_lakes and saves the final data to a CSV file. Appends data to the existing CSV if it exists.

    Parameters:
        selected_lakes (list): List of lake names to process. If None, process all lakes.
        output_dir (str): Path to save the final output files as well as query for existing data. If None, defaults to "../Data.
        geojson_path (str): Path to the input geojson file containing lake outlines.
        **kwargs: Additional arguments for filter_pixc_file function.
    """
    """
    Process each lake: search for multiple SWOT collections, filter pixel files, and aggregate results.
    """
    if pixel_names is None:
        pixel_names = ['SWOT_L2_HR_PIXC_D']  # default
    
    # Process files
    for pixc_file in tqdm(files, desc="Processing PIXC files", unit="file"):
        # Reset this for each file if you want 1 parquet per PIXC granule
        current_file_rows = []
        
        rows = filter_pixc_file(
            pixc_file=pixc_file,
            kwargs=kwargs
        )
        
        if rows:
            current_file_rows.extend(rows)
            
            flattened_rows = [flatten_dict(row) for row in current_file_rows]
            df = pd.DataFrame(flattened_rows).dropna(how='all')
            
            if not df.empty:
                os.makedirs(output_dir, exist_ok=True)

                base_name = os.path.basename(pixc_file).replace('.nc', '')
                pixc_parquet_file = os.path.join(output_dir, f'{base_name}.parquet')
            
                df.to_parquet(pixc_parquet_file,
                              # engine='fastparquet',
                              index=False)
            else:
                print(f"DataFrame empty after filtering for: {pixc_file}")
        else:
            print(f"No points passed filters for: {pixc_file}")

        # 6. Cleanup (Ensure temp_dir is defined in your main or globally)
        if 'temp_dir' in locals() or 'temp_dir' in globals():
            safe_rmtree(temp_dir) 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter and write out PIXC data.")
   
    parser.add_argument("--version", type=str, default="D")
    parser.add_argument("--date", type=str, help="YYYY_MM_DD")

    args = parser.parse_args()

    # Use args.version instead of just version
    if args.version == 'D':
        pixel_names = ['SWOT_L2_HR_PIXC_D']
        output_dir = '/nas/cee-ice/data/SWOT/PIXC_filtered_vD'
        
    elif args.version == '2_0':
        pixel_names = ['SWOT_L2_HR_PIXC_2.0']
        output_dir = '/nas/cee-ice/data/SWOT/PIXC_filtered_v2_0'

    parent_dir = '/nas/cee-ice/data/SWOT/'
    
    # files = getFiles(data_dir)

    # index = int(os.environ['SLURM_ARRAY_TASK_ID'])
    # print(index)

    # indices = pd.read_csv('/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/PIXC_vD_indices.csv')
    # start = indices.iloc[index, 1]
    # stop = indices.iloc[index, 2]

    # t0 = time.time()

    json_path = os.path.join(parent_dir,
                             f'files_to_filter_v{args.version}_{args.date}.json')
    with open(json_path, 'r') as f:
        files = json.load(f)
    
    total_files = len(files)
    
    task_id = int(os.environ.get('SLURM_ARRAY_TASK_ID', 0))
    chunk_size = 1000
    
    # Calculate indices
    start = task_id * chunk_size
    stop = min((task_id + 1) * chunk_size, total_files)
    
    # Safety check for the last job
    if stop == total_files:
        print(f"Final Job {task_id}: Successfully capped at {stop}")
    
    # Slice the list
    current_batch = files[start:stop]
    
    print(f"Task {task_id} processing {len(current_batch)} files (Indices: {start} to {stop})")

    files = files[start:stop]

    files_to_process = []

    # Check to be sure we didn't already process
    for f in files:
        granule = os.path.basename(f).replace('.nc', '')
        output_file = os.path.join(output_dir, f'{granule}.parquet')
        
        if not os.path.isfile(output_file):
            files_to_process.append(f)

    default_args = dict(
        classification_vals = [2, 3, 4, 5, 6, 7],
        # water_classification = [4], # UPDATED WATER CLASSIFICATION
        bitwise_qual_max = 65536,
        geolocation_qual_th = 65536,
        sig0_qual_th = 65536,
        interferogram_qual_th = 65536,
        classification_qual_th = 65536,
        target_crs = "EPSG:4326"  # WGS84 (longitude, latitude)
    )
    
    start_time = time.time()    
    main(files=files_to_process, output_dir=output_dir, kwargs=default_args, pixel_names=pixel_names) 
    
    # Backup cleanup step in case we error out before removing temp files
    temp_dir = os.path.join(parent_dir, "_temp")
    if os.path.exists(temp_dir):
        safe_rmtree(temp_dir)        
               
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")