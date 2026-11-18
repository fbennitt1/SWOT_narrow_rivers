import json

import geopandas as gpd
import numpy as np
import pandas as pd

from scipy.stats import linregress
from shapely.geometry import *

def specialBuffer(df, width_col, cap_style, segmented=False, extra=False):
    '''
    XXX
    '''
    # print(df.index)
    if segmented == True:
        reach = df.segments
    else:
        reach = df.geometry
    
    half_width = df[width_col]/2
    
    if extra == True:
        buffer = reach.buffer(distance=(half_width+32), cap_style=cap_style)
    else:
        buffer = reach.buffer(distance=half_width, cap_style=cap_style)
    return buffer
    
def specialClip(df):
    '''
    XXX
    '''
    left = gpd.GeoSeries(df.pseudo_geom)
    right = gpd.GeoSeries(df.buffers)
    pseudo_geom_clip = left.clip(right)
    return pseudo_geom_clip

def specialDissolve(reach):
    '''
    XXX
    '''
    reach = reach.dissolve(by='counter', as_index=False)
    return reach

def open_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        return data
    
def project_point(line, point):
    '''
    XXX
    '''
    # Project point onto line
    return line.project(point)

def group_regress(group):
    '''
    XXX
    '''
    # group = group.filter(lambda x: x['agg_wse'] == 1)
    
    if (len(group) > 2) and (len(group['distance'].unique()) > 1):
        slope, _, r, _, se = (linregress(x=group['distance'], y=group['wse']))
        return pd.Series(
            {'swot_slope': slope, 'swot_r': r, 'swot_se': se}
        )
    else:
        return pd.Series(
            {'swot_slope': np.nan, 'swot_r': np.nan, 'swot_se': np.nan}
        )
    
# def getFilepaths(data_path, huc2, huc4s, width_set):
#     file_paths = []
    
#     for huc in huc4s:
#         file_path = data_path + 'NHDPLUS_H_' + huc + '_HU4_GDB_prepped_buffered_extra_' + width_set + '.parquet'
#         file_paths.append(file_path)
        
#     return file_paths
    