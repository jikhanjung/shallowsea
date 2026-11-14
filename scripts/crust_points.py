"""CRUST1.0 대륙지각 표본점과 PALEOMAP v3 회전, PaleoDEM 읽기를 여러 스크립트가 같이 쓴다."""
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
# CRUST1.0 유형 묶음(CNtype1_key.txt). 마스크에 남는 유형만 적는다.
TYPE_GROUPS = {
    'margin': ('C-','S-','T-','U-','V2','W-'),
    'precambrian_craton': ('D-','E-','F-','G1','G2','H1','H2','I1','I2'),
    'phanerozoic_orogen_arc_rift': ('L1','L2','M-','N-','O-','P-','Q-','R1','R2','X-','Z1','Z2','Y1'),
}
DEM_NAME = re.compile(r'Map([\d.]+)_PALEOMAP_(?:1deg|6min)_.*?_(\d+(?:\.\d+)?)Ma\.nc$')


def load_points():
    """대륙지각 셀을 네 사분면 중심점으로 나눈 표본. 경도·위도·유형·두께·면적(km²)·부피(km³)."""
    with zipfile.ZipFile(INPUTS / 'crust-thick.zip') as archive:
        lon, lat, thickness = np.loadtxt(archive.open('crsthk.xyz')).T
    with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as archive:
        kind = np.loadtxt(archive.extractfile('CNtype1-1.txt'), dtype=str).ravel()
    keep = ~np.isin(kind, OCEAN_OR_AMBIGUOUS)
    lon, lat, thickness, kind = (v[keep] for v in (lon, lat, thickness, kind))
    # Sample each CRUST1.0 cell at the centres of four 0.5-degree quadrants.
    lon = (lon[:,None]+[-.25,.25,-.25,.25]).ravel()
    lat = (lat[:,None]+[-.25,-.25,.25,.25]).ravel()
    thickness = np.repeat(thickness,4)
    kind = np.repeat(kind,4)
    area = RADIUS**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))
    return lon, lat, kind, thickness, area, area*thickness


class Plates:
    """현대 PALEOMAP v3 폴리곤으로 점마다 판 ID를 정하고, 시점마다 고위치를 돌려준다."""

    def __init__(self, lon, lat):
        self.model = pg.RotationModel(str(INPUTS / 'PALEOMAP_PlateModel.rot'))
        features = [f for f in pg.FeatureCollection(str(INPUTS / 'PALEOMAP_PlatePolygons.gpml'))
                    if f.get_valid_time()[0] >= 0 >= f.get_valid_time()[1]]
        partition = pg.PlatePartitioner(features,self.model,
            sort_partitioning_plates=pg.SortPartitioningPlates.by_partition_type_then_plate_area)
        points = [pg.PointOnSphere(float(y),float(x)) for y,x in zip(lat,lon)]
        self.plate_id = np.full(len(points),-1)
        self.names = {}
        for i,point in enumerate(points):
            hit = partition.partition_point(point)
            if hit is not None:
                pid = hit.get_feature().get_reconstruction_plate_id()
                self.plate_id[i] = pid
                self.names.setdefault(int(pid), hit.get_feature().get_name())
        self.groups = {int(pid):np.flatnonzero(self.plate_id==pid) for pid in np.unique(self.plate_id) if pid>=0}
        self.clouds = {pid:pg.MultiPointOnSphere([points[i] for i in ii]) for pid,ii in self.groups.items()}

    def paleo(self, age):
        """시점 age(Ma)의 고위도·고경도. 판이 없거나 회전이 없으면 NaN."""
        plat = np.full(len(self.plate_id),np.nan)
        plon = np.full(len(self.plate_id),np.nan)
        for pid,indices in self.groups.items():
            rotation=self.model.get_rotation(age,pid,from_time=0,use_identity_for_missing_plate_ids=False)
            if rotation is None:
                continue
            coords=(rotation*self.clouds[pid]).to_lat_lon_array()
            plat[indices]=coords[:,0]
            plon[indices]=coords[:,1]
        return plat, plon


def atlas_levels():
    """PaleoDEM 지도 번호(1° 배포본) → 그 지도를 그린 아틀라스 판들 [{'level', 'tract', 'atlas_map'}].
    대응은 그림과 DEM을 겹친 검사(results/atlas_sea_level_check.csv, devlog 008)를 따른다."""
    import csv
    out = {}
    with open(ROOT / 'results/atlas_sea_level_check.csv') as f:
        for r in csv.DictReader(f):
            out.setdefault(r['matched_dem_map'], []).append(
                {'level': int(r['caption_sea_level_m']), 'tract': r['systems_tract'], 'atlas_map': r['atlas_map']})
    return out


def dem_files(archive_name):
    """zip 안의 PaleoDEM 이름을 (지도 번호, 나이, 이름)으로. macOS 리소스 포크는 뺀다."""
    with zipfile.ZipFile(INPUTS / archive_name) as archive:
        names = [n for n in archive.namelist() if DEM_NAME.search(n) and not Path(n).name.startswith('._')]
    return [(DEM_NAME.search(n)[1].lstrip('0'), float(DEM_NAME.search(n)[2]), n) for n in names]


def read_dem(archive_name, name, shape):
    """PaleoDEM 하나를 (위도 90 → −90, 경도 −180 → 180) 격자로 읽는다."""
    with zipfile.ZipFile(INPUTS / archive_name) as archive, tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / 'grid.nc'
        source.write_bytes(archive.read(name))
        raw = Path(tmp) / 'grid.bin'
        subprocess.check_call(['gdal_translate', '-q', '-of', 'ENVI', str(source), str(raw)])
        grid = np.fromfile(raw, dtype=np.float32).reshape(shape)
    assert np.isfinite(grid).all()
    return grid


def sample(grid, plat, plon, step):
    """격자점 등록 격자에서 고위치의 최근접 값. 위치가 NaN이면 NaN."""
    n_lon = grid.shape[1] - 1
    valid = np.isfinite(plat)
    z = np.full(len(plat), np.nan)
    ix = np.floor(plon[valid]/step + 180/step + .5).astype(int) % n_lon
    iy = np.clip(np.floor(90/step - plat[valid]/step + .5).astype(int), 0, grid.shape[0]-1)
    z[valid] = grid[iy, ix]
    return z
