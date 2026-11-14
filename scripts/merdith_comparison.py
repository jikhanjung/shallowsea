"""그때 없던 지괴와 판 겹침을 Merdith et al. (2021) 판 모델로 다시 낸다 (devlog 019).

PALEOMAP 정의(devlog 005): 그때 없던 지괴 = PALEOMAP으로 되돌린 CRUST1.0 표본점이 Scotese PaleoDEM에서 물가 아래
1,400 m보다 깊고 얕은 곳에서 3°보다 먼 곳에 놓임. [칠한 값]에 기댄다.
Merdith 정의(이 스크립트): 그 시점에 유효한 Merdith 대륙 다각형(Continents/shapes_continents.gpml, 다각형마다
나타나는 나이와 사라지는 나이가 있다) 어디에도 들지 않는 표본점. 다각형 기하는 현재 좌표에 있으므로, 그 시점에
유효한 다각형을 현재 좌표에서 그대로 써서 표본점의 소속과 판 번호를 정한다. 지도의 깊이와 무관하다.
현재(0 Ma) Merdith 대륙 다각형 밖의 CRUST1.0 대륙지각(약 8.2백만 km²)은 Merdith 정의의 모집단에서 뺀다.

판 겹침은 alignment.coverage와 같은 셈이다(1° 고격자에서 판이 둘 이상 들어온 셀의 점 면적 합이 셀 면적을 넘는 양).
두 모델을 같은 점에서 비교하려고, 두 정의에서 모두 있는 점만으로 낸 겹침도 적는다.
출력: results/merdith_comparison.csv (면적 백만 km²)
"""
import collections
import csv

import numpy as np
import pygplates as pg

import alignment as al
from crust_points import INPUTS, ROOT, dem_files, read_dem, sample
from far_terrane_groups import REGIONS

MODEL = INPUTS / 'merdith2021/v1.2.4'
rotation = pg.RotationModel(str(MODEL / 'Rotations/1000_0_rotfile_Merdith_etal.rot'))
continents = [f for f in pg.FeatureCollection(str(MODEL / 'Continents/shapes_continents.gpml'))
              if f.get_geometry() is not None]
points = [pg.PointOnSphere(float(y), float(x)) for y, x in zip(al.lat, al.lon)]
area = al.area


def membership(age):
    """age에 유효한 Merdith 대륙 다각형으로 표본점의 판 번호를 정한다(없으면 −1)."""
    chosen = []
    for f in continents:
        begin, end = f.get_valid_time()
        if begin >= age >= end:
            c = f.clone()   # 현재 좌표의 기하를 그대로 쓰려고 유효 시간을 풀어 0 Ma에서 나눈다
            c.set_valid_time(pg.GeoTimeInstant.create_distant_past(), pg.GeoTimeInstant.create_distant_future())
            chosen.append(c)
    partition = pg.PlatePartitioner(chosen, rotation,
                                    sort_partitioning_plates=pg.SortPartitioningPlates.by_partition_type_then_plate_area)
    pid = np.full(len(points), -1)
    for i, p in enumerate(points):
        hit = partition.partition_point(p)
        if hit is not None:
            pid[i] = hit.get_feature().get_reconstruction_plate_id()
    return pid


def paleo(pid, age):
    plat = np.full(len(pid), np.nan)
    plon = np.full(len(pid), np.nan)
    for q in np.unique(pid[pid >= 0]):
        idx = np.flatnonzero(pid == q)
        r = rotation.get_rotation(float(age), int(q), 0.0, use_identity_for_missing_plate_ids=False)
        if r is None:
            continue
        xy = (r * pg.MultiPointOnSphere([points[i] for i in idx])).to_lat_lon_array()
        plat[idx], plon[idx] = xy[:, 0], xy[:, 1]
    return plat, plon


def overlap(plat, plon, use, pid):
    iy, ix = al.cell_index(plat[use], plon[use])
    flat = iy * 360 + ix
    total = np.bincount(flat, weights=area[use], minlength=181 * 360)
    pids = collections.defaultdict(set)
    for f, p in zip(flat, pid[use]):
        pids[f].add(p)
    multi = np.zeros(181 * 360, bool)
    multi[[f for f, s in pids.items() if len(s) > 1]] = True
    return np.clip(total - np.repeat(al.cell_area, 360), 0, None)[multi].sum() / 1e6


def main():
    present = membership(0) >= 0
    region = np.full(al.plates.plate_id.shape, 'other', dtype=object)
    for k, (_, ids) in REGIONS.items():
        region[np.isin(al.plates.plate_id, ids)] = k
    rows = []
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        pid = membership(age)
        absent = present & (pid < 0)
        mlat, mlon = paleo(pid, age)
        mvalid = np.isfinite(mlat)
        common = valid & ~far & mvalid & present
        row = {'age_ma': f'{age:g}', 'map': map_no,
               'paleomap_tracked_area': area[valid].sum() / 1e6,
               'paleomap_far_area': area[far].sum() / 1e6,
               'paleomap_overlap': overlap(plat, plon, valid, al.plates.plate_id),
               'merdith_population_area': area[present].sum() / 1e6,
               'merdith_absent_area': area[absent].sum() / 1e6,
               'merdith_overlap': overlap(mlat, mlon, mvalid, pid),
               'far_and_absent_area': area[far & absent].sum() / 1e6,
               'common_area': area[common].sum() / 1e6,
               'paleomap_overlap_common': overlap(plat, plon, common, al.plates.plate_id),
               'merdith_overlap_common': overlap(mlat, mlon, common, pid)}
        for k in list(REGIONS) + ['other']:
            m = region == k
            row[f'{k}_far'] = area[m & far].sum() / 1e6
            row[f'{k}_absent'] = area[m & absent].sum() / 1e6
            row[f'{k}_far_and_absent'] = area[m & far & absent].sum() / 1e6
        rows.append(row)
    with open(ROOT / 'results/merdith_comparison.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
