"""회전한 CRUST1.0 대륙지각과 PaleoDEM이 서로 맞는지 본다 (devlog 005, P01 2단계).

출력
- results/alignment_summary.csv: 109개 시점마다 깊은 곳(해수면 0에서 1,400 m보다 깊음)에 놓인 대륙지각을
  유형 묶음·얕은 곳까지 거리별로 나누고, 1°와 0.1° 읽기, 판 겹침, 지각 없는 DEM 대륙을 함께 적는다.
- results/alignment_plates.csv: 500, 260, 240 Ma에서 판별 깊은 면적과 현대 위치.
- results/alignment_age_shift.csv: 회전 나이를 ±5, ±10 Myr 비틀었을 때 맞음 지표.
"""
import collections
import csv

import numpy as np

from crust_points import RADIUS, ROOT, TYPE_GROUPS, Plates, dem_files, load_points, read_dem, sample

DEEP = -1400
SHALLOW = -200
PLATE_AGES = (500, 260, 240)
SHIFT_AGES = (20, 50, 100, 150, 200, 260, 300, 350, 400, 450, 500, 540)

lon, lat, kind, thickness, area, volume = load_points()
plates = Plates(lon, lat)
group = np.full(len(kind), '', dtype=object)
for name, kinds in TYPE_GROUPS.items():
    group[np.isin(kind, kinds)] = name
assert (group != '').all()
craton = group == 'precambrian_craton'
cell_lat = np.arange(90, -91, -1.)
bounds = np.deg2rad(np.clip(np.stack([cell_lat - .5, cell_lat + .5]), -90, 90))
cell_area = RADIUS**2 * np.deg2rad(1) * np.diff(np.sin(bounds), axis=0)[0]  # 1° 격자 한 행의 셀 면적(km²)


def mm(a):
    return a.sum() / 1e6


def cell_index(plat, plon):
    """고위치를 1° 격자(181 × 360, 경도 −180 ~ 179)의 행·열로."""
    iy = np.clip(np.floor(90.5 - plat).astype(int), 0, 180)
    ix = np.floor(plon + 180.5).astype(int) % 360
    return iy, ix


def distance_class(shallow, iy, ix):
    """얕은 셀까지의 거리(격자 칸 수, 경도는 위도와 상관없이 1°로 센다): 1, 3, 그보다 멂(99)."""
    dist = np.full(len(iy), 99)
    for k in (3, 1):
        grown = np.pad(shallow, ((k, k), (0, 0)))
        out = np.zeros_like(shallow)
        for dy in range(-k, k + 1):
            for dx in range(-k, k + 1):
                out |= np.roll(grown, dx, axis=1)[k + dy:k + dy + shallow.shape[0]]
        dist[out[iy, ix]] = k
    return dist


def coverage(plat, plon, valid):
    """1° 고격자에서 판 겹침과 셀 채움. 겹침 = 판이 둘 이상 들어온 셀에서 점 면적 합이 셀 면적을 넘는 양."""
    iy, ix = cell_index(plat[valid], plon[valid])
    flat = iy * 360 + ix
    total = np.bincount(flat, weights=area[valid], minlength=181 * 360)
    pids = collections.defaultdict(set)
    for f, pid in zip(flat, plates.plate_id[valid]):
        pids[f].add(pid)
    multi = np.zeros(181 * 360, bool)
    multi[[f for f, s in pids.items() if len(s) > 1]] = True
    capacity = np.repeat(cell_area, 360)
    overlap = np.clip(total - capacity, 0, None)[multi].sum() / 1e6
    occupied = (total > 0).reshape(181, 360)
    # 겹친 셀의 점 면적을 셀 면적에 맞게 줄이는 비율. 지도상 중복 제거 면적에 쓴다.
    scale = np.ones(181 * 360)
    over = multi & (total > capacity)
    scale[over] = capacity[over] / total[over]
    factor = np.ones(len(plat))
    factor[valid] = scale[flat]
    return overlap, occupied, factor


def main():
    atlas = collections.defaultdict(list)
    with open(ROOT / 'docs/paleoatlas_sea_levels.csv') as f:
        for r in csv.DictReader(f):
            atlas[r['atlas_map']].append(int(r['sea_level_m']))
    files_1 = {round(a): (m, n) for m, a, n in dem_files('dem.zip')}
    files_6 = {round(a): (m, n) for m, a, n in dem_files('dem_6min.zip')}
    z_modern = sample(read_dem('dem_6min.zip', files_6[0][1], (1801, 3601)), lat, lon, 0.1)
    summary, plate_rows = [], []
    for key in sorted(files_1):
        map_no, name = files_1[key]
        age = [a for m, a, n in dem_files('dem.zip') if n == name][0]
        g1 = read_dem('dem.zip', name, (181, 361))
        g6 = read_dem('dem_6min.zip', files_6[key][1], (1801, 3601))
        plat, plon = plates.paleo(age)
        valid = np.isfinite(plat)
        z1, z6 = sample(g1, plat, plon, 1.0), sample(g6, plat, plon, 0.1)
        deep = valid & (z1 < DEEP)
        iy, ix = cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        dist = distance_class(g1[:, :360] >= SHALLOW, iy, ix)
        overlap, occupied, factor = coverage(plat, plon, valid)
        dedup = area * factor
        # DEM에서 −200 m 이상인데 그 셀과 이웃 셀에 추적 지각이 하나도 없는 면적.
        near_crust = np.zeros_like(occupied)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near_crust |= np.roll(np.roll(occupied, dy, 0), dx, 1)
        dem_continent = g1[:, :360] >= SHALLOW
        uncovered = (dem_continent & ~near_crust) * cell_area[:, None]
        ok = valid & (z_modern > 0) & (z6 > 0)
        row = {
            'age_ma': f'{age:g}', 'map': map_no,
            'submerged_1deg': mm(area[valid & (z1 < 0)]), 'submerged_6min': mm(area[valid & (z6 < 0)]),
            'deep_1deg': mm(area[deep]), 'deep_6min': mm(area[valid & (z6 < DEEP)]),
            **{f'deep_{g}': mm(area[deep & (group == g)]) for g in TYPE_GROUPS},
            'deep_within_1deg_of_shallow': mm(area[deep & (dist == 1)]),
            'deep_within_3deg_of_shallow': mm(area[deep & (dist <= 3)]),
            'deep_farther_than_3deg': mm(area[deep & (dist == 99)]),
            'craton_on_continent_share': area[craton & valid & (z6 >= SHALLOW)].sum() / area[craton & valid].sum(),
            'elevation_correlation': np.corrcoef(z_modern[ok], z6[ok])[0, 1],
            'plate_overlap': overlap,
            'dedup_area': mm(dedup[valid]),
            'dedup_submerged_sea_level_0': mm(dedup[valid & (z1 < 0)]),
            'dedup_submerged_atlas_min': mm(dedup[valid & (z1 < min(atlas[map_no]))]) if map_no in atlas else '',
            'dedup_submerged_atlas_max': mm(dedup[valid & (z1 < max(atlas[map_no]))]) if map_no in atlas else '',
            'tracked_submerged_atlas_max': mm(area[valid & (z1 < max(atlas[map_no]))]) if map_no in atlas else '',
            'dem_continent_without_crust': uncovered.sum() / 1e6,
            'dem_continent': (dem_continent * cell_area[:, None]).sum() / 1e6,
        }
        summary.append(row)
        if key in PLATE_AGES:
            for pid, idx in plates.groups.items():
                if not deep[idx].any():
                    continue
                w = area[idx]
                kinds = collections.Counter()
                for k, a in zip(kind[idx], w):
                    kinds[k] += a
                x = np.average(np.cos(np.deg2rad(lon[idx])), weights=w)
                y = np.average(np.sin(np.deg2rad(lon[idx])), weights=w)
                plate_rows.append({
                    'age_ma': f'{age:g}', 'plate_id': pid, 'area': mm(w), 'deep': mm(w[deep[idx]]),
                    'deep_farther_than_3deg': mm(w[deep[idx] & (dist[idx] == 99)]),
                    'modern_lat_min': lat[idx].min(), 'modern_lat_max': lat[idx].max(),
                    'modern_lon_center': np.rad2deg(np.arctan2(y, x)),
                    'main_types': ' '.join(k for k, _ in kinds.most_common(3)),
                })
    shift_rows = []
    for key in SHIFT_AGES:
        g6 = read_dem('dem_6min.zip', files_6[key][1], (1801, 3601))
        age = [a for m, a, n in dem_files('dem_6min.zip') if n == files_6[key][1]][0]
        for shift in (-10, -5, 0, 5, 10):
            plat, plon = plates.paleo(age + shift)
            z6 = sample(g6, plat, plon, 0.1)
            ok = np.isfinite(z6) & (z_modern > 0) & (z6 > 0)
            on = craton & np.isfinite(z6)
            shift_rows.append({'age_ma': f'{age:g}', 'shift_myr': shift,
                               'elevation_correlation': np.corrcoef(z_modern[ok], z6[ok])[0, 1],
                               'craton_on_continent_share': area[on & (z6 >= SHALLOW)].sum() / area[on].sum()})
    for path, rows in (('alignment_summary.csv', summary), ('alignment_plates.csv', plate_rows),
                       ('alignment_age_shift.csv', shift_rows)):
        with open(ROOT / 'results' / path, 'w', newline='') as f:
            writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
            writer.writeheader()
            for r in rows:
                writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
