import csv
import io
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import zipfile

import numpy as np
import pygplates as pg

RADIUS = 6371.0088
OCEAN_OR_AMBIGUOUS = ('A0','A1','B-','V1','Y3','J-','K-','Y2')
ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'inputs'

with zipfile.ZipFile(INPUTS / 'crust-thick.zip') as archive:
    lon, lat, thickness = np.loadtxt(archive.open('crsthk.xyz')).T
with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as archive:
    kind = np.loadtxt(archive.extractfile('CNtype1-1.txt'), dtype=str).ravel()
keep = ~np.isin(kind, OCEAN_OR_AMBIGUOUS)
lon, lat, thickness = (v[keep] for v in (lon,lat,thickness))
# Sample each CRUST1.0 cell at the centres of four 0.5-degree quadrants.
lon = (lon[:,None]+[-.25,.25,-.25,.25]).ravel()
lat = (lat[:,None]+[-.25,-.25,.25,.25]).ravel()
thickness = np.repeat(thickness,4)
area = RADIUS**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))
volume = area*thickness

model = pg.RotationModel(str(INPUTS / 'PALEOMAP_PlateModel.rot'))
features = [f for f in pg.FeatureCollection(str(INPUTS / 'PALEOMAP_PlatePolygons.gpml'))
            if f.get_valid_time()[0] >= 0 >= f.get_valid_time()[1]]
partition = pg.PlatePartitioner(features,model,
    sort_partitioning_plates=pg.SortPartitioningPlates.by_partition_type_then_plate_area)
points = [pg.PointOnSphere(float(y),float(x)) for y,x in zip(lat,lon)]
plate_id = np.full(len(points),-1)
for i,point in enumerate(points):
    hit = partition.partition_point(point)
    if hit is not None:
        plate_id[i] = hit.get_feature().get_reconstruction_plate_id()
groups = {int(pid):np.flatnonzero(plate_id==pid) for pid in np.unique(plate_id) if pid>=0}
clouds = {pid:pg.MultiPointOnSphere([points[i] for i in ii]) for pid,ii in groups.items()}
print('area assigned',area[plate_id>=0].sum()/1e6,'of',area.sum()/1e6, 'plates',len(groups),flush=True)

categories = ('land','sea_level','shallow_0_to_150m','shallow_150_to_200m','deeper_than_200m','unresolved')
def summarize(z,valid):
    masks = (z>0,z==0,(z<0)&(z>=-150),(z<-150)&(z>=-200),z<-200,~valid)
    stats = [v for mask in masks for v in (area[mask].sum()/1e6,volume[mask].sum()/1e9)]
    assert np.isclose(sum(stats[::2]),area.sum()/1e6)
    assert np.isclose(sum(stats[1::2]),volume.sum()/1e9)
    return stats

rows=[]
with zipfile.ZipFile(INPUTS / 'dem.zip') as archive,tempfile.TemporaryDirectory() as tmp:
    for name in archive.namelist():
        match=re.search(r'_(\d+(?:\.\d+)?)Ma\.nc$',name)
        if not match:
            continue
        age=float(match[1])
        path=Path(tmp)/'grid.nc'
        path.write_bytes(archive.read(name))
        grid=np.loadtxt(io.BytesIO(subprocess.check_output(
            ['gdal_translate','-q','-of','XYZ',str(path),'/vsistdout/']))).reshape(181,361,3)
        assert np.allclose(grid[0,:,0],np.arange(-180,181))
        assert np.allclose(grid[:,0,1],np.arange(90,-91,-1))
        assert np.isfinite(grid).all()
        z=np.full(len(area),np.nan)
        for pid,indices in groups.items():
            rotation=model.get_rotation(age,pid,from_time=0,use_identity_for_missing_plate_ids=False)
            if rotation is None:
                continue
            coords=(rotation*clouds[pid]).to_lat_lon_array()
            ix=np.floor(coords[:,1]+180.5).astype(int)%360
            iy=np.clip(np.floor(90.5-coords[:,0]).astype(int),0,180)
            z[indices]=grid[iy,ix,2]
        stats=summarize(z,np.isfinite(z))
        rows.append([age,*stats,stats[4]+stats[6],stats[5]+stats[7]])
        if age in (0,66,65,100,150,200,210,240,250,260,300,350,400,425,450,500,535):
            print(age,np.round(stats,3),flush=True)
assert len({x[0] for x in rows}) == len(rows) == 109
with open(ROOT / 'results/PALEOMAP_CRUST1_0-540Ma.csv','w',newline='') as f:
    writer=csv.writer(f,lineterminator='\n')
    writer.writerow(['age_ma']+[f'{name}_{units}' for name in categories for units in ('million_km2','billion_km3')]+['shallow_0_to_200m_million_km2','shallow_0_to_200m_billion_km3'])
    writer.writerows([f"{row[0]:g}", *(f"{value:.5f}" for value in row[1:])] for row in sorted(rows,reverse=True))
