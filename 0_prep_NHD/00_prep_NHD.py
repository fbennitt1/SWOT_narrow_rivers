import os

import geopandas as gpd
import math
import numpy as np
import pandas as pd

from shapely.ops import linemerge

def calc_az_sin(df): ### NEW WAY, RIGHT
    '''
    orthogonal, 09/11/2025 thanks to Ellie
    https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2016GL072089
    '''
    # Extract coordinates
    line = df.geometry
    x_coords = [coord[0] for coord in line.coords]
    y_coords = [coord[1] for coord in line.coords]
    coords = np.array([x_coords, y_coords]).T

    # print(x_coords)
    # print(y_coords)
    
    # Center the data
    x_mean = np.mean(x_coords)
    y_mean = np.mean(y_coords)
    # print(x_mean)
    # print(y_mean)

    centered = coords - [x_mean, y_mean]
    
    # PCA for orthogonal regression
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eig(cov)
    principal_direction = eigvecs[:, np.argmax(eigvals)]
    
    # Calculate azimuth from principal direction
    azimuth = math.degrees(math.atan2(principal_direction[1],
                                      principal_direction[0]))
    if azimuth < 0:
        azimuth += 360

    # Sinuosity
    dx = x_coords[-1] - x_coords[0]
    dy = y_coords[-1] - y_coords[0]
    distance = np.sqrt(dx**2 + dy**2)
    sinuosity = line.length / distance

    return azimuth, sinuosity

def prepNHD(data_path, save_path, index):
    '''
    This function takes a filepath to the NHD HR Plus,
    merges on the VAA and EROMMA tables, intersects the flowlines with
    the waterbodies and discards those that are within, finds the
    physiographic division for each reach, and calculates the width for
    each reach. It writes out the merged HUC4 files as parquet.
    '''
    ## Set-up
    mdata_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
    # Max binsize of 1000 is plenty for CONUS w/o lakes
    # Mississippi is ~472 m wide at mouth as calculated here
    bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 150, 200, 500, 1000]
    
    # Define dtypes for lookup tables to preserve leading zeros
    dtype_dic= {'HUC4': str, 'HUC2': str, 'toBasin': str, 'level': str}
    # Read in HUC lookup table
    lookup = pd.read_csv(os.path.join(mdata_path,
                                      'HUC4_lookup_no_great_lakes.csv'),
                         dtype=dtype_dic)
    
    # Get current HUC2 and HUC4 IDs
    huc2 = f'HUC2_{lookup.loc[index,'HUC4'][0:2]}'
    huc4 = f'NHDPLUS_H_{lookup.loc[index,'HUC4']}_HU4_GDB'

    # Set data filepath
    file_path = os.path.join(data_path, huc2, huc4, huc4 + '.gdb')
    
    # Set write filepath
    save_path = os.path.join(save_path, huc2)
    # save_file = huc4 + '_prepped.gpkg'
    save_file = f'{huc4}_prepped.parquet'
    
    ## Prep Physiographic Regions
    # https://www.sciencebase.gov/catalog/item/631405bbd34e36012efa304e
    physio = gpd.read_file(filename=os.path.join(data_path,
                                                 'other_shapefiles/physio.shp'),
                           engine='pyogrio')
    # Set CRS to Web Mercator
    physio = physio.to_crs(epsg=3857)
    # Dissolve provinces by division
    physio = physio.dissolve(by='DIVISION').reset_index()
    # Drop all columns besides division and geometry
    physio = physio[['DIVISION', 'geometry']]
    
    ## Get bankfull width coefficients from Bieber et al. 2015, Table 3
    bankfull = pd.read_csv(os.path.join(mdata_path,
                                        'bieger_2015_bankfull_width.csv'))

    ## Merging
    # Read in NHD flowlines
    basin = gpd.read_file(filename=file_path, layer='NHDFlowline',
                          engine='pyogrio')
    # Set CRS to Pseudo-Mercator https://epsg.io/3857
    basin = basin.to_crs(epsg=3857)
    # Merge the MultiLineStrings so they play nice with cal_az_sin
    basin['temp'] = basin['geometry'].apply(linemerge)
    basin = basin.drop(columns='geometry')
    basin = basin.rename(columns = {'temp': 'geometry'}).set_geometry('geometry')

    # Read in VAA
    vaa = gpd.read_file(filename=file_path, layer='NHDPlusFlowlineVAA',
                        engine='pyogrio')
    # Merge on VAA
    basin = basin.merge(right=vaa, how='inner', on=['NHDPlusID',
                                                    'VPUID',
                                                    'ReachCode'])
    # Read in EROMMA
    eromma = gpd.read_file(filename=file_path, layer='NHDPlusEROMMA',
                           engine='pyogrio')
    # Merge on EROMMA
    basin = basin.merge(right=eromma, how='inner', on=['NHDPlusID', 'VPUID'])

    # Read in EROMQAMA
    eromqama = gpd.read_file(filename=file_path, layer='NHDPlusEROMQAMA',
                             engine='pyogrio')

    # Merge on GaugeIDs
    basin = basin.merge(right=eromqama[['NHDPlusID', 'GageID',
                                        'GageRef', 'VPUID']],
                        how='left', on=['NHDPlusID', 'VPUID'])
    
    del vaa, eromma, eromqama
    print(f'\nSize of df pre-filtering: {basin.shape[0]}\n')
    
    ## Filtering
    area = gpd.read_file(filename=file_path, layer='NHDWaterbody',
                         columns=['NHDPlusID', 'geometry'], engine='pyogrio')
    # Set CRS to Pseudo-Mercator https://epsg.io/3857
    area = area.to_crs(epsg=3857)
    
    # Find all flowlines within waterbodies
    subset = basin.sjoin(df=area, how='inner', predicate='within')
    # Get IDs of these flowlines
    ids = subset.NHDPlusID_left.to_list()
    del subset
    # Drop reaches within waterbodies
    basin = basin[~basin.NHDPlusID.isin(ids)]
    print(f'\nSize of df after filtering waterbodies: {basin.shape[0]}\n')

    # Read in SWOT Science orbit swath
    swath = gpd.read_parquet('/nas/cee-ice/data/SWOT/swath/swot_science_hr_Aug2021-v05_shapefile_swath_dissolved.parquet')
    # Set CRS to Pseudo-Mercator https://epsg.io/3857
    swath = swath.to_crs(epsg=3857)

    # Find all flowlines within swath
    subset = gpd.sjoin(left_df=basin, right_df=swath,
                      how='inner', predicate='within')
        # Get IDs of these flowlines
    ids = subset.NHDPlusID.to_list()
    del subset
    # Drop reaches within nadir gap
    basin = basin[basin.NHDPlusID.isin(ids)]
    print(f'\nSize of df after filtering gaps: {basin.shape[0]}\n')
    
    # Drop reaches that aren't stream types or artificial path
    basin = basin.loc[(basin.FType == 460) | (basin.FType == 558)]
    # Drop reaches that are terminal paths
    basin = basin.loc[basin.TerminalFl == 0]
    # Drop reaches with discharge of zero
    basin = basin.loc[basin.QBMA > 0]
    # Drop reaches with stream order of zero
    basin = basin.loc[basin.StreamOrde > 0]

    ## Find the physiographic division each reach is within
    # Using intersects to foil the broken topology even after the dissolve
    # and neither shapely nor sf fully repaired it
    basin = basin.sjoin(df=physio, how='left',
                        predicate='intersects').drop(columns='index_right')
    # Drop all reaches where DIVISION == NaN (in Canada and off the coast)
    basin = basin[~basin.DIVISION.isnull()]

    ## Calculate attributes
    # Get sinuosity and azimuth
    # basin[['Azimuth', 'Sinuosity']] = basin.apply(calc_az_sin, axis=1)
    
    basin['temp'] = basin.apply(calc_az_sin, axis=1)
    basin[['Azimuth', 'Sinuosity']] = pd.DataFrame(basin['temp'].tolist(),
                                                   index=basin.index)
    basin = basin.drop(columns='temp')
    
    ## Get bankfull widths
    # Merge on bankfull width coefficient
    basin = basin.merge(right=bankfull, on='DIVISION', how='left')
    # Calculate width from cumulative drainage area
    basin['WidthM'] = basin.a*basin.TotDASqKm**basin.b
    
    # Calculate the multiplicative factor from the standard error
    # of estimate for each physiographic division (SEEpd) by exponentiation
    basin['mul_factor'] = 10**basin.see_phys
    # Calculate the min width of each reach
    basin['WidthM_Min'] = basin.WidthM/basin.mul_factor
    # Calculate the max width of each basin
    basin['WidthM_Max'] = basin.WidthM*basin.mul_factor
    
    # Drop reaches that are shorter than their width
    basin = basin[basin['LengthKM']*1000 > basin['WidthM']]

    ## Bin reaches by width, set to string for parquet
    basin['Bin'] = pd.cut(basin['WidthM'], bins).astype(str)
    basin['Bin_Min'] = pd.cut(basin['WidthM_Min'], bins).astype(str)
    basin['Bin_Max'] = pd.cut(basin['WidthM_Max'], bins).astype(str)

    # ## Write out gdf as gpkg file
    # if not os.path.isdir(save_path):
    #     os.makedirs(save_path)
    # basin.to_file(os.path.join(save_path, save_file), driver='GPKG')
    
    ## Write out gdf as parquet
    if not os.path.isdir(save_path):
        os.makedirs(save_path, exist_ok=True)
    basin.to_parquet(os.path.join(save_path, save_file))

    print('Script completed, wrote out!')
    
slurm = int(os.environ['SLURM_ARRAY_TASK_ID'])
print(slurm)

if __name__ == "__main__":
    data_path = '/nas/cee-ice/data/NHDPlus_HR/'
    save_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/NHD_prepped/'

    prepNHD(data_path=data_path, save_path=save_path, index=slurm)