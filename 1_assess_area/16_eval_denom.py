from argparse import ArgumentParser
import datetime
import os
import sys
# import time

import dask.dataframe as dd
import dask_geopandas as dg
import geopandas as gpd
import numpy as np
import pandas as pd
# import shapely
import xarray as xr

from pandarallel import pandarallel

sys.path.insert(1, '../0_prep_NHD/')
from reaches import *
from utils import *

def evalStats(width_set, index, cpus_per_task, huc2, suffix, swot_dir, nhd_dir,
              mdata_dir, save_dir):

    ## SET UP
    if width_set == 'mean':
        width = 'WidthM'
        binn = 'Bin'
    elif width_set == 'min':
        width = 'WidthM_Min'
        binn = 'Bin_Min'
    elif width_set == 'max':
        width = 'WidthM_Max'
        binn = 'Bin_Max'
    else:
        print('Invalid width option specified, exiting.')

    ### PIXEL CLOUD
    file_path = f'{mdata_dir}PIXC_vD_HUC2_{huc2}_filtered_{suffix}.json'
    data = open_json(file_path)
    file_name = data[index]
    
    # # Get PIXC filepath
    # files = os.listdir(swot_dir)
    # file_name = files[index]
    
    # Get PIXC metadata
    granule_name = file_name[:-3]
    tile_name = file_name[20:28]
    pass_num = int(file_name[20:23])

    print(granule_name)

    ## Find correct HUC4s
    # Read in tile and HUC4 intersection data
    dtype_dic= {'tile': str, 'huc4': str, 'coverage': float}
    tile_huc4 = pd.read_csv(os.path.join(mdata_dir,
                                        'huc4_swot_science_tiles.csv'),
                            dtype=dtype_dic)
    
    # Make list of HUC4s that intersect the tile
    huc4s = list(tile_huc4[tile_huc4['tile'] == tile_name]['huc4'])
    # Limit to the current HUC2
    huc4s = [x for x in huc4s if x.startswith(huc2)]

    ## Read in PIXC
    # PIXC datapath
    pixc_path = os.path.join(swot_dir, file_name)
    print(f'PIXC path: {pixc_path}')

    # Read in pixel group
    ds_PIXC = xr.open_mfdataset(paths=pixc_path,
                                group = 'pixel_cloud',
                                engine='h5netcdf')


    ### Calculate stats on data filtering
    ## WITHOUT FULL FILTER
    # Make mask
    mask = denomMask(ds_PIXC)

    # Filtering for cross-track does not count against the denominator,
    # as we are not supposed to use these extreme pixels for analysis.
    if mask.shape[0] == 0:
        print('Condition 0: This granule has no pixels pre-qual filter, exiting.') 
        sys.exit()

    # Set desired data vars
    variables = ['cross_track', 'water_frac', 'pixel_area',
                 'classification_qual', 'geolocation_qual',
                 'interferogram_qual', 'classification']

    # Convert PIXC to GeoDataFrame
    gdf_PIXC = makeGDF(ds=ds_PIXC, mask=mask, data_vars=variables)

    # del ds_PIXC

    # Write out the pixels that fall within the 10 to 60 km range
    # and nwhose class != land
    save_path = f'{save_dir}/HUC2_{huc2}_vD_pre_filter/'
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    gdf_PIXC[['points', 'cross_track', 'water_frac', 'pixel_area',
              'classification_qual', 'geolocation_qual', 'interferogram_qual',
              'klass']].to_parquet(
        os.path.join(save_path, f'{granule_name}.parquet')
    )

    ## Read in buffered flowlines with extra width
    data_path = f'{nhd_dir}NHD_prepped_buffered_extra/HUC2_{huc2}/'

    #
    file_paths = []
    for huc in huc4s:
        file_path = f'{data_path}NHDPLUS_H_{huc}_HU4_GDB_prepped_buffered_extra_{width_set}.parquet'
        file_paths.append(file_path)

    # Read in
    reach_mask = dg.read_parquet(path=file_paths,
                                 columns=['NHDPlusID', width, binn, 'buffers'])

    reach_mask = reach_mask.compute()

    # Clip masked pixels to buffered reaches
    gdf_PIXC = gpd.sjoin(gdf_PIXC, reach_mask,
                         how='inner', predicate='within').reset_index().drop(columns=['index', 'index_right']
    )

    if gdf_PIXC.shape[0] == 0:
        print('Condition 1: This granule has no pixels that intersect reaches pre-qual filter, exiting.')      
        
        sys.exit()

    #
    gdf_PIXC = gdf_PIXC.reset_index().drop(
        columns=['index', 'latitude', 'longitude', 'geometry']
    )

    # 
    save_path = f'{save_dir}/HUC2_{huc2}_vD_pre_filter_in_reach/'
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    gdf_PIXC.to_parquet(os.path.join(save_path, f'{granule_name}.parquet'))

    ## WITH FULL FILTER
    # Make mask
    mask = bitwiseMask(ds_PIXC)

    # Filtering for cross-track does not count against the denominator,
    # as we are not supposed to use these extreme pixels for analysis.
    if mask.shape[0] == 0:
        print('Condition 2: This granule has no pixels post-qual filter, exiting.')
        sys.exit()
        
    # Set desired data vars
    variables = ['cross_track', 'water_frac', 'pixel_area',
                 'classification_qual', 'geolocation_qual',
                 'interferogram_qual', 'classification']

    # Convert PIXC to GeoDataFrame
    gdf_PIXC = makeGDF(ds=ds_PIXC, mask=mask, data_vars=variables)

    # del ds_PIXC

    # Write out the pixels that fall within the 10 to 60 km range
    save_path = f'{save_dir}/HUC2_{huc2}_vD_post_filter/'
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    gdf_PIXC[['points', 'cross_track', 'water_frac', 'pixel_area',
              'classification_qual', 'geolocation_qual', 'interferogram_qual',
              'klass']].to_parquet(
        os.path.join(save_path, f'{granule_name}.parquet')
    )

    # Clip masked pixels to buffered reaches
    gdf_PIXC = gpd.sjoin(gdf_PIXC, reach_mask,
                         how='inner', predicate='within').reset_index().drop(columns=['index', 'index_right']
    )

    if gdf_PIXC.shape[0] == 0:
        print('Condition 3: This granule has no pixels that intersect reaches post-qual filter, exiting.')
        sys.exit()

    #
    gdf_PIXC = gdf_PIXC.reset_index().drop(
        columns=['index', 'latitude', 'longitude', 'geometry']
    )

    # 
    save_path = f'{save_dir}/HUC2_{huc2}_vD_post_filter_in_reach/'
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    gdf_PIXC.to_parquet(os.path.join(save_path, f'{granule_name}.parquet'))

    print('Script completed, wrote out results.')

# --------------------
    
### PARSE ARGUMENTS
parser = ArgumentParser(
    description =
    'Please specify whether you would like to use \
    the min, mean, or max predicted bankfull width \
    for this analysis.'
)

parser.add_argument('width_set', type=str, help='min, mean, or max')
args = parser.parse_args()
width_set = args.width_set

print('width_set: ' + width_set)

### GET JOB INDEX, CPUS
task = int(os.environ['SLURM_ARRAY_TASK_ID'])
cpus = int(os.environ.get('SLURM_CPUS_PER_TASK'))
cpus_per_task = cpus if cpus < 65 else 1

# Get the current date
current_date = datetime.date.today()
date_string = current_date.strftime("%Y_%m_%d")

if __name__ == "__main__":
    huc2 = '03' #'03', '15', '17'
    suffix = '1'
    
    swot_dir = f'/nas/cee-ice/data/SWOT/PIXC_vD/'
    nhd_dir = f'/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/'
    mdata_dir = f'/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
    save_dir = f'/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_pixel_stats/'
    
    evalStats(width_set=width_set, index=task, cpus_per_task=cpus_per_task,
              huc2=huc2, suffix=suffix, swot_dir=swot_dir, nhd_dir=nhd_dir,
              mdata_dir=mdata_dir, save_dir=save_dir)