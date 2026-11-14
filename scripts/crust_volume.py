"""Scotese 지형이 그리는 대륙의 고도를 대륙지각 두께로 바꿔 부피가 현재와 같은지 본다 (devlog 011).

1. 보정: 현대 CRUST1.0 대륙지각 1° 셀에서 물·얼음 하중을 뺀 고도(dry, airy_sensitivity.py와 같은 계산)와
   지각 두께(crsthk)의 관계를 100 m 구간별 면적 가중 평균으로 만들고 보간한다. 관계는 직선이 아니다
   (해수면 아래 연변에서 가파르고, 0–2,000 m에서 37–40 km로 평평하다).
2. 시점마다 회전한 표본점이 놓인 PaleoDEM(1°) 값을 dry 고도로 바꾼다. 바다(값 < 0)는 바닷물 하중을 빼
   dry = 값 × k(k = 1 − 1.03/3.30). 표본점 면적 × 두께(dry)를 더해 부피를 낸다.
3. 부피를 현재(같은 방법으로 0 Ma 지도에서 낸 값)와 같게 맞추려면 그 시점의 대륙 전체를 몇 m 올려야 하는지(δ)를
   구한다. δ > 0이면 Scotese가 부피 보존 대륙보다 낮게 그린 것이고, 해수면을 그만큼 높게 둔 것과 같다.
면적: 추적 면적, 판 겹침을 셀 면적에 맞게 줄인 면적, 거기서 그때 없던 지괴(devlog 005)를 뺀 면적.
출력: results/crust_volume.csv, results/crust_volume_calibration.csv
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, dem_files, read_dem, sample
from independent_sea_level import K, modern_relief

BIN = 100


def calibration():
    """dry 고도 → 두께(km) 보간표. 구간 중심과 면적 가중 평균 두께."""
    import tarfile
    import zipfile
    from crust_points import INPUTS, OCEAN_OR_AMBIGUOUS
    with zipfile.ZipFile(INPUTS / 'crust-thick.zip') as f:
        lon, lat, thickness = np.loadtxt(f.open('crsthk.xyz')).T
    with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as f:
        kind = np.loadtxt(f.extractfile('CNtype1-1.txt'), dtype=str).ravel()
    thickness = thickness[~np.isin(kind, OCEAN_OR_AMBIGUOUS)]
    area, dry = modern_relief()
    edges = np.arange(-4000, 6001, BIN)
    centres, means, areas = [], [], []
    for lo in edges[:-1]:
        m = (dry >= lo) & (dry < lo + BIN)
        if area[m].sum() > 0.05:          # 백만 km² 미만 구간은 건너뛰고 보간한다
            centres.append(lo + BIN / 2)
            means.append(np.average(thickness[m], weights=area[m]))
            areas.append(area[m].sum())
    return np.array(centres), np.array(means), np.array(areas)


def main():
    centres, means, areas = calibration()
    thick = lambda d: np.interp(d, centres, means)
    rows = []
    reference = None
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        dry = np.where(z < 0, z * K, z)
        _, _, factor = al.coverage(plat, plon, valid)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        weights = {'tracked': np.where(valid, al.area, 0.0),
                   'dedup': np.where(valid, al.area * factor, 0.0),
                   'dedup_without_far': np.where(valid & ~far, al.area * factor, 0.0)}
        row = {'age_ma': f'{age:g}', 'map': map_no}
        for key, w in weights.items():
            row[f'{key}_area'] = w.sum() / 1e6
            row[f'{key}_mean_dry_m'] = float(np.average(np.nan_to_num(dry), weights=w))
            row[f'{key}_volume'] = float(np.sum(w * thick(np.nan_to_num(dry)))) / 1e9
        rows.append(row)
        if reference is None:
            reference = {key: row[f'{key}_volume'] for key in weights}   # 0 Ma
    # δ: 그 시점의 대륙을 통째로 몇 m 올려야 현재 부피(0 Ma 지도의 추적 면적 부피, 부피 일정 가설)와 같아지는가.
    # 면적 정의마다 따로 구한다. 판 겹침이나 그때 없던 지괴를 빼면 같은 부피를 더 좁은 대륙이 담아야 한다.
    target = reference['tracked']
    for row, (map_no, age, name) in zip(rows, sorted(dem_files('dem.zip'), key=lambda r: r[1])):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        dry = np.nan_to_num(np.where(z < 0, z * K, z))
        _, _, factor = al.coverage(plat, plon, valid)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        weights = {'tracked': np.where(valid, al.area, 0.0),
                   'dedup': np.where(valid, al.area * factor, 0.0),
                   'dedup_without_far': np.where(valid & ~far, al.area * factor, 0.0)}
        for key, w in weights.items():
            lo, hi = -3000.0, 6000.0
            for _ in range(60):
                mid = (lo + hi) / 2
                if np.sum(w * thick(dry + mid)) / 1e9 < target:
                    lo = mid
                else:
                    hi = mid
            row[f'{key}_offset_to_present_volume_m'] = (lo + hi) / 2
            row[f'{key}_volume_ratio'] = row[f'{key}_volume'] / target
    with open(ROOT / 'results/crust_volume.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})
    with open(ROOT / 'results/crust_volume_calibration.csv', 'w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['dry_elevation_m', 'mean_thickness_km', 'area_million_km2'])
        writer.writerows([f'{c:g}', f'{m:.3f}', f'{a:.4f}'] for c, m, a in zip(centres, means, areas))
    area, dry = modern_relief()
    print('modern CRUST1 volume via calibration %.3f e9 km3 (crsthk 6.891); 0 Ma Scotese DEM tracked %.3f'
          % (np.dot(area * 1e6, thick(dry)) / 1e9, reference['tracked']))


if __name__ == '__main__':
    main()
