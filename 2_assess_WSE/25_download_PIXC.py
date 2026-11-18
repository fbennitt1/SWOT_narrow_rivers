import json
import os
import sys

import earthaccess
import pandas as pd

with open('/nas/cee-ice/data/SWOT/redownload_vD_2026_03_27.json', 'r') as f:
    data_list = json.load(f)

print(f'{len(data_list)}')

# download
earthaccess.download(data_list[0:5000],
                     f'/nas/cee-ice/data/SWOT/PIXC_vD',
                     threads=4)
print('First 5000 done.')

# download
earthaccess.download(data_list[5000:len(data_list)],
                     f'/nas/cee-ice/data/SWOT/PIXC_vD',
                     threads=4)
print(f'{len(data_list)} done.')

# granules = pd.read_parquet('/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/usgs_gauge_swot_granules_vD_2026_03_23.parquet')

# links_list_clean = granules['granule'].to_list()
# print(f'{len(links_list_clean)}')

# # download
# earthaccess.download(links_list_clean[0:5000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=8)
# print('First 5000 done.')

# # download
# earthaccess.download(links_list_clean[5000:10000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 10000 done.')

# # download
# earthaccess.download(links_list_clean[10000:15000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 15000 done.')

# download
# earthaccess.download(links_list_clean[15000:20000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 20000 done.')

# # download
# earthaccess.download(links_list_clean[20000:25000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 25000 done.')

# # download
# earthaccess.download(links_list_clean[25000:30000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 30000 done.')

# # download
# earthaccess.download(links_list_clean[30000:35000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 35000 done.')

# # download
# earthaccess.download(links_list_clean[35000:40000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 40000 done.')

# # download
# earthaccess.download(links_list_clean[40000:45000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 45000 done.')

# # download
# earthaccess.download(links_list_clean[45000:50000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 50000 done.')

# # download
# earthaccess.download(links_list_clean[50000:55000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 55000 done.')

# # download
# earthaccess.download(links_list_clean[55000:60000],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('First 60000 done.')

# # download
# earthaccess.download(links_list_clean[60000:66503],
#                      f'/nas/cee-ice/data/SWOT/PIXC_vD',
#                      threads=4)
# print('66503 done.')

# Exit the script
sys.exit(0)