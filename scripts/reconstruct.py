"""CRUST1.0 대륙지각을 PALEOMAP v3로 109개 시점에 돌려 PaleoDEM 1°에서 고도를 읽고 면적·부피를 집계한다 (devlog 001, 004)."""
import csv

import numpy as np

from crust_points import ROOT, Plates, dem_files, load_points, read_dem, sample

lon, lat, kind, thickness, area, volume = load_points()
plates = Plates(lon, lat)
print('area assigned',area[plates.plate_id>=0].sum()/1e6,'of',area.sum()/1e6, 'plates',len(plates.groups),flush=True)

categories = ('land','sea_level','shallow_0_to_150m','shallow_150_to_200m','deeper_than_200m','unresolved')
def summarize(z,valid):
    masks = (z>0,z==0,(z<0)&(z>=-150),(z<-150)&(z>=-200),z<-200,~valid)
    stats = [v for mask in masks for v in (area[mask].sum()/1e6,volume[mask].sum()/1e9)]
    assert np.isclose(sum(stats[::2]),area.sum()/1e6)
    assert np.isclose(sum(stats[1::2]),volume.sum()/1e9)
    return stats

# 물가 기준(devlog 004): 해수면 0과 PaleoAtlas 지도에 적힌 해수면. 정수 번호 지도만 아틀라스 설정이 있다.
atlas={}
with open(ROOT / 'docs/paleoatlas_sea_levels.csv') as f:
    for r in csv.DictReader(f):
        atlas.setdefault(r['atlas_map'],[]).append(int(r['sea_level_m']))
def submerged(z,valid,level):
    """물가 level(m) 기준 육지·물가·잠김·잠김 중 물가 아래 1,400 m보다 깊음·미해결의 면적(백만 km²)과 부피(십억 km³)."""
    masks=(valid&(z>level),valid&(z==level),valid&(z<level),valid&(z<level-1400),~valid)
    stats=[v for mask in masks for v in (area[mask].sum()/1e6,volume[mask].sum()/1e9)]
    assert np.isclose(sum(stats[0:6:2])+stats[8],area.sum()/1e6)
    return stats
waterline_rows=[]

rows=[]
for map_no,age,name in dem_files('dem.zip'):
    plat,plon=plates.paleo(age)
    z=sample(read_dem('dem.zip',name,(181,361)),plat,plon,1.0)
    stats=summarize(z,np.isfinite(z))
    valid=np.isfinite(z)
    waterline_rows.append([age,map_no,'sea_level_0',0,*submerged(z,valid,0)])
    for level in sorted(set(atlas.get(map_no,[]))):
        waterline_rows.append([age,map_no,'atlas',level,*submerged(z,valid,level)])
    rows.append([age,*stats,stats[4]+stats[6],stats[5]+stats[7]])
    if age in (0,66,65,100,150,200,210,240,250,260,300,350,400,425,450,500,535):
        print(age,np.round(stats,3),flush=True)
assert len({x[0] for x in rows}) == len(rows) == 109
with open(ROOT / 'results/PALEOMAP_CRUST1_0-540Ma.csv','w',newline='') as f:
    writer=csv.writer(f,lineterminator='\n')
    writer.writerow(['age_ma']+[f'{name}_{units}' for name in categories for units in ('million_km2','billion_km3')]+['shallow_0_to_200m_million_km2','shallow_0_to_200m_billion_km3'])
    writer.writerows([f"{row[0]:g}", *(f"{value:.5f}" for value in row[1:])] for row in sorted(rows,reverse=True))

with open(ROOT / 'results/PALEOMAP_CRUST1_waterline_0-540Ma.csv','w',newline='') as f:
    writer=csv.writer(f,lineterminator='\n')
    writer.writerow(['age_ma','map','waterline','sea_level_m']+[f'{name}_{units}' for name in
        ('land','at_waterline','submerged','submerged_deeper_than_1400m','unresolved') for units in ('million_km2','billion_km3')])
    writer.writerows([f"{r[0]:g}",r[1],r[2],r[3],*(f"{v:.5f}" for v in r[4:])]
                     for r in sorted(waterline_rows,key=lambda r:(-r[0],r[2]!='sea_level_0',r[3])))
