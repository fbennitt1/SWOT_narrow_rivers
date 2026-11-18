import os
import sys

import earthaccess
import pandas as pd

bad_masks = [
'12026400',
'13333000',
'14174000',
'14302900',
'14332000',
'14337600',
'11123000', ###
'08063100',
'08066250',
'08086212',
'08173000',
'08185000',
'08316000',
'09085100',
'06919500',
'06932000',
'07018500',
'07019000',
'07026040', # trib
'07036100', # split?
'07060710', # triangle
'07062500', # trib?
'07077380',
'07103800',
'07126200', # tail
'07167500', # triangle
'07171000', # tail
'07242380', # tail
'07301110', # long
'07375500',
'08012000',
'08015500',
'08018500',
'08019000',
'08025500',
'08041500',
'08055500',
'08061000',
'06018500',
'06036650',
'06177000', # short
'06183450',
'06214500', # trib
'06294000', # long
'06306300', # long
'06339500', # long
'06342260',
'06425100',
'06605850', # multichannel
'06720820', # long
'06809210', # SUPER LONG
'06894000', # long
'04115000', # long
'04146063',
'04180000', # long
'04206000', # long--I measure ~ 20 m, drainage says 55, area says 137
'04224775', # long
'04258000', # long
'04275000', # long
'04282525', # chopped
'05069000', # chopped, too wide
'05079000', # a little long
'05099600', # blocky, meandering rapidly
'05100000', # super long
'05378500', # many dams!!!!
'05437500', # super long, drainage says 75, area says 300
'05502300', # super long
'05517500', # long
'05518000', # too long, multi-channel
'0423205010', # bit long
'03225500', # super long
'03271500', # super long
'03276500', # a bit long
'03303000', # short, area over estimate
'03303280', # short, dam (OK??)
'03321350', # super long
'03333450', # long
'03353600', # long
'03360000', # short, area over est
'03361500', # long
'03364500', # long
'03374000', # trib
'03378550', # super long
'03378635', # long
'03413200', # super long
'03417500', # super long, capturing trib not main stem!
'03418420', # super long
'03446000', # long
'03451500', # long
'03567500', # long
'03568933', # long
'04033000', # long
'04094000', # long
'04097500', # trib
'04101000', # SO LONG, capturing trib not main stem!
'04105700', # SO LONG, capturing trib not main stem! width fine, weird!
'02350600', # long
'02353400', # super long
'02359170', # width overestimate, capturing entire network
'02368000', # width overestimate, multichannel
'02375500', # width overestimate, capturing trib
'02414715', # long
'02423630', # quite long
'03020500', # super long
'03028000', # long
'03031500', # short, no dams
'03085000', # dam, above and below, includes trib, gauge above dam
'03094000', # width overestimate, capturing entire network
'03164000', # capturing trip in addition to main stem, stem mask okay
'03176500', # short, no dams
'03189100', # super long
'03212500', # includes trib
'01613000', # long
'01619500', # long
'01650500', # quite long
'02049500', # long, new width wrong
'02065500', # quite long
'02089000', # long
'02102500', # short, no dams, area width better than drainage
'02105769', # side channel not trib, but includes water below 'rock arch'
'02110500', # SUPER LONG, drainage 40 m, area 260 m
'02112000', # includes quite a bit of tributary
'02133624', # long, clipped the meander not up and downstream
'02136000', # looks like it captured side channel, not mainstem
'02152100', # long, might not be centered
'02173500', # weirdly clipped, i think area might be wrong
'02202600', # weird, i think area might be wrong
'02227500', # very curved, clipping meander downstream
'02329600', # wrong huc!!! and wrong mask
'0208758850', # too long, below dam, not getting upstream of gauge
'01208925', # not sure mask is right
'01327750', # capturing the entire network, area width 250, discharge area 123, what is going on
'01350355', # long, only capturing upstream
'01371500', # quite long, only capturing upstream
'01375000', # quite long, below dam (correctly) but only capturing downstream
'01377500', # wuite long, eidth very overestimated from area
'01378500', # capturing entire network, below dam (correctly)
'01381900', # weirdly clipped, something wrong, area width double drainage
'01387000', # capturing entire network, below dam (correctly)
'01411000', # too long, not sure why
'01468500', # too long, area width about triple
'01480685', # too long, width about right, below dam (correctly)
'01521500', # capturing entire network, just below dry dam (captures rain)
'01553500', # includes a very long trib
'01570500', # includes a very long trib
'01576000', # includes a very long trib, new width almost 3x
'01017000', # long, only includes downstream, width overestimate
'01019000', # long, area width estimate 8x
'01022500', # long, area with 2x
'02450180', # a little long
'03048500', # a little long
'03058975', # a little long
'03213700', # a little long
'02020500', # a little long
'02051000', # a little long
'02071000', # a little long
'01388500', # a little long
'01609000', # a little long
'01043500', # quite long, below dam (correctly), both width estimates 2x (though wider just downstream)
'01054500', # seems to be only trib, below dam (correctly)
'01060000', # a little long, above dam (correctly)? new width 3x
'01085500', # a little long, area width estimate 3x, below dam (correctly)
'01087000', # captures entire network, not sure why, new width 5x
'01096000', # a little long, new width 3x
'01101000', # weirdly clipped, missing meander gage is on
'01123360', # long, gage located in spillway of dam?? only giving below
'01133000', # a little lon, area estimate 2x
'01138500', # capturing only trib, drainage width 1.5x, new width 50 m more
'01152500', # too long, only capturing below, split channel so width overest
'01154500', # a bit long, drainage width close, new width 5x, only below gage?
'01158000',  # a bit long, drainage 1.5x estimate, area '01158000'  # a bit long, drainage 1.5x estimate, area 2.5x, below dam
# '02444160', # mask failed, at dam and lock
'03206600', # much too long, both wdith estimates 2x too large
'05512500'] # too short, width estimates fine, wrong part of river?

# Table of all gauges with NHDPlus HR reaches mapped
nhd_sites = pd.read_parquet('/nas/cee-water/cjgleason/fiona/USGS_gauges/usgs_stations_with_stage_and_nhd_metadata.parquet',
                            columns=['site_id', 'name'])

masks = pd.read_parquet('/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC_data/nhd_reach_masks_for_gauges_combined.parquet')

# Remove the masks deemed bad via manual inspection
masks = masks[~masks['site_id'].isin(bad_masks)]

# Drop NAs
masks = masks[~masks['reach_mask'].isna()]

# Merge on names
masks = masks.merge(nhd_sites, on='site_id')

# Remove the reaches at dams/locks, for now (but keep "ADAMS"!)
temp_mask = (
    ((masks['name'].str.contains('DAM', case=False))
    | (masks['name'].str.contains('L&D', case=False))
    | (masks['name'].str.contains('LOCK', case=False))
    )
    & ~masks['name'].str.contains('ADAMS', case=False)
)
masks = masks[~temp_mask].reset_index()

print(masks.shape)

site_ids = masks['site_id'].to_list()

mdata_path = '/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/'
dtype_dic = {'tile': str, 'site_id': str}
lookup = pd.read_csv(os.path.join(mdata_path,
                                  'usgs_gauges_swot_science_tiles.csv'),
                     dtype=dtype_dic)

lookup = lookup[lookup['site_id'].isin(site_ids)]

# Get list of tiles
tiles = list(lookup['tile'])

tiles = list(set(tiles))
tiles.sort()

tiles = [tile + '*' for tile in tiles]
tiles = ['*' + tile for tile in tiles]

# Full Version D science orbit (thus far)
# start = '2025-05-05 00:00:00'
# start = '2023-07-26 00:00:00'
start = '2024-08-19 00:00:00'
# end = '2025-11-30 23:59:59'
end = '2026-03-23 00:00:00'

missing = []
links_list = []

for tile in tiles:
    print(tile)
    try:
        pixc_results = earthaccess.search_data(
            short_name = 'SWOT_L2_HR_PIXC_D', # Version D
            # short_name = 'SWOT_L2_HR_PIXC_2.0', # Version C
            temporal = (start, end),
            granule_name = tile
        )

        for i in range(len(pixc_results)):
            pixc_link = earthaccess.results.DataGranule.data_links(pixc_results[i], access='external')[0]
            # print(pixc_link)
            links_list.append(pixc_link)
    
    except:
        missing.append(tile)

print(missing)

# Make DataFrame of granule names
granules = pd.DataFrame({'granule': links_list})

# FOR PRIOR
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

granules.to_parquet('/nas/cee-water/cjgleason/fiona/narrow_rivers_PIXC/data/usgs_gauge_swot_granules_vD_2026_03_23.parquet')
