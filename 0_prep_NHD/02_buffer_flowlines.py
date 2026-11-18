import os
import sys
import time

import geopandas as gpd
import pandas as pd

from argparse import ArgumentParser
from pandarallel import pandarallel

from reaches import readNHD
from utils import specialBuffer

def bufferNHD(width_set, extra, index, cpus_per_task):
    # Control flow
    if width_set == 'mean':
        width = 'WidthM'
    elif width_set == 'min':
        width = 'WidthM_Min'
    elif width_set == 'max':
        width = 'WidthM_Max'
    else:
        print('Invalid width option specified, exiting.')
        
    # Initialize parallel
    pandarallel.initialize(nb_workers=cpus_per_task)
    
    ## Prepare data
    # Read NHD
    df, huc4, huc2 = readNHD(index=slurm, segmented=False)

    # Buffer flowlines with an extra 32 m on each side to be safe
    # This is just beyond the max distance that the pixels could
    # extend once converted to pseudo pixels
    if extra == 'extra':
        df['buffers'] = df.parallel_apply(
            user_defined_function=specialBuffer,
            args=(width, 'flat', False, True), # args are cap_style, segmented, extra
            axis=1)
    else:
        df['buffers'] = df.parallel_apply(
            user_defined_function=specialBuffer,
            args=(width, 'flat', False, False), # args are cap_style, segmented, extra
            axis=1)
        
    # Drop original reach geometry column, set buffered geometry as
    # active geometry
    df = df.drop(columns='geometry') \
        .set_geometry('buffers').set_crs(crs=df.crs)

    # Calculate segment area
    df['reach_area'] = df.geometry.area
    
    ## Write out
    # Set write filepath
    if extra == 'extra':
        save_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/NHD_prepped_buffered_extra/'
        save_file = f'{huc4}_prepped_buffered_extra_{width_set}.parquet'

    else:
        save_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/NHD_prepped_buffered/'
        save_file = f'{huc4}_prepped_buffered_{width_set}.parquet'
        
    save_path = os.path.join(save_path, huc2)
    
    #Write out gdf as parquet file
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    df.to_parquet(os.path.join(save_path, save_file))
    
    print('Script completed, wrote out results.')
    
### PARSE ARGUMENTS
parser = ArgumentParser(
    description =
    'Please specify whether you would like to use \
    the min, mean, or max predicted bankfull width \
    for this analysis as well as whether you would \
    like extra buffer.'
)

parser.add_argument('width_set', type=str, help='min, mean, or max')
parser.add_argument('extra', type=str, help='extra, no')
args = parser.parse_args()
width_set = args.width_set
extra = args.extra

print('width_set: ' + width_set)

### GET JOB INDEX, CPUS
slurm = int(os.environ['SLURM_ARRAY_TASK_ID'])
cpus = int(os.environ.get('SLURM_CPUS_PER_TASK'))
cpus_per_task = cpus if cpus < 65 else 1

if __name__ == "__main__":
    bufferNHD(width_set=width_set, extra=extra, index=slurm,
              cpus_per_task=cpus_per_task)