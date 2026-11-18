import os

import earthaccess 
import pandas as pd

mdata_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
dtype_dic = {'tile': str, 'huc4': str, 'coverage': float}
lookup = pd.read_csv(os.path.join(mdata_path,
                                  'huc4_swot_science_tiles.csv'),
                     dtype=dtype_dic)

huc2 = '17' # '01' '03' '15' '17'
huc2_01 = lookup[lookup['huc4'].str.startswith(huc2)]

# Get list of tiles
tiles = list(huc2_01['tile'])

# Remove duplicates
tiles = list(set(tiles))
tiles.sort()

tiles = [tile + '_*' for tile in tiles]
tiles = ['*_' + tile for tile in tiles]

# Full Version D science orbit (thus far)
# start = '2025-05-05 00:00:00'
start = '2023-07-26 00:00:00'
end = '2025-11-30 23:59:59'
# end = '2025-05-05 00:00:00'

missing = []
links_list = []

for tile in tiles:
    print(tile)
    try:
        pixc_results = earthaccess.search_data(short_name = 'SWOT_L2_HR_PIXC_D',
            # short_name = 'SWOT_L2_HR_PIXC_2.0',
                                               temporal = (start, end),
                                               granule_name = tile)

        for i in range(len(pixc_results)):
            pixc_link = earthaccess.results.DataGranule.data_links(pixc_results[i], access='external')[0]
            # print(pixc_link)
            links_list.append(pixc_link)
    
    except:
        missing.append(tile)

print(missing)

# Make DataFrame of granule names
granules = pd.DataFrame({'granule': links_list})

granules['cycle'] = granules['granule'].str.slice(115,118)
granules['pass'] = granules['granule'].str.slice(119,122)
granules['tile'] = granules['granule'].str.slice(123,127)
granules['version'] = granules['granule'].str.slice(-10,-6)
granules['counter'] = granules['granule'].str.slice(-5,-3)

# Sort the files
granules = granules.sort_values(by=['cycle', 'pass', 'tile', 'version', 'counter'],
                                ascending=[True, True, True, True, False])

# Keep only the best version of each granule
granules = granules.drop_duplicates(subset=['cycle', 'pass', 'tile'], keep='first')

granules.to_parquet(f'/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/huc2_{huc2}_vD_granules.parquet')