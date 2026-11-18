import os
import sys

import earthaccess
import pandas as pd

granules = pd.read_parquet('/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/huc2_03_vD_granules.parquet')

links_list_clean = granules['granule'].to_list()
print(f'{len(links_list_clean)}')

# download
earthaccess.download(links_list_clean[0:5000],
                     f'/nas/cee-ice/data/SWOT/PIXC_vD',
                     threads=8)

# download
earthaccess.download(links_list_clean[5000:10000],
                     f'/nas/cee-ice/data/SWOT/PIXC_vD',
                     threads=8)

# download
earthaccess.download(links_list_clean[10000:],
                     f'/nas/cee-ice/data/SWOT/PIXC_vD',
                     threads=8)


# Exit the script
sys.exit(0)