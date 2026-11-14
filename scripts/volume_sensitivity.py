"""부피 검사(devlog 011)의 민감도: 대륙이 등압평형이 아닌 이유(동적 지형 등)로 일정 높이만큼 눌려 있었다면 (devlog 015).

Scotese 고도에 Δ(0–400 m)를 더한 고도를 등압평형 고도로 보고 두께로 바꾼다. 곧 "Scotese가 그린 고도 = 등압평형 고도 − Δ"
(Δ는 동적 지형·열 상태 등으로 눌린 높이)라고 본다. 면적 정의는 겹침과 그때 없던 지괴를 뺀 셋째 정의다.
출력: results/volume_sensitivity.csv
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, dem_files, read_dem, sample
from crust_volume import calibration
from independent_sea_level import K

OFFSETS = (0, 100, 200, 250, 300, 400)


def main():
    centres, means, _ = calibration()
    thick = lambda d: np.interp(d, centres, means)
    rows, reference = [], None
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        dry = np.nan_to_num(np.where(z < 0, z * K, z))
        _, _, factor = al.coverage(plat, plon, valid)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        w = np.where(valid & ~far, al.area * factor, 0.0)
        if reference is None:
            reference = float(np.sum(np.where(valid, al.area, 0.0) * thick(dry)))   # 0 Ma 추적 면적 부피
        row = {'age_ma': f'{age:g}', 'area_ratio': w.sum() / al.area.sum()}
        for d in OFFSETS:
            row[f'volume_ratio_offset_{d}'] = float(np.sum(w * thick(dry + d))) / reference
            row[f'thickness_ratio_offset_{d}'] = float(np.sum(w * thick(dry + d)) / w.sum()) / (reference / al.area.sum())
        rows.append(row)
    with open(ROOT / 'results/volume_sensitivity.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
