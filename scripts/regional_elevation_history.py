"""Scotese 지도에서 지역별 안정지괴의 고도를 시대별로 따라간다 (devlog 017).

질문: 아프리카는 지금 초팽창으로 약 +700 m 떠받쳐져 있다(현재 잔차 지형, devlog 015). Scotese 지도는 현대 지형을
돌려 고친 것이므로, 그 높이가 고생대 지도에 옮겨졌는가?
방법: 시점마다 회전한 CRUST1.0 선캄브리아 안정지괴 표본점(그때 없던 지괴 제외, 겹침은 셀 면적에 맞게 줄임)의
PaleoDEM 고도(바다는 바닷물 하중을 뺀 dry 고도)를 지역별로 면적 가중 평균하고, 같은 표본점의 0 Ma 값과 비교한다.
지역은 PALEOMAP 판 번호 첫 자리(crust_volume_by_region.py와 같음).
출력: results/regional_elevation_history.csv
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, TYPE_GROUPS, dem_files, read_dem, sample
from crust_volume_by_region import GROUPS
from independent_sea_level import K


def main():
    first = np.array([int(str(p)[0]) if p >= 0 else 0 for p in al.plates.plate_id])
    craton = np.isin(al.kind, TYPE_GROUPS['precambrian_craton'])
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
        w = np.where(valid & ~far & craton, al.area * factor, 0.0)
        if reference is None:
            reference = dry.copy()
        row = {'age_ma': f'{age:g}'}
        for g, label in GROUPS.items():
            m = (first == g) & (w > 0)
            row[f'{g}_area'] = w[m].sum() / 1e6
            row[f'{g}_mean_dry_m'] = float(np.average(dry[m], weights=w[m])) if m.any() else ''
            row[f'{g}_same_points_0ma_m'] = float(np.average(reference[m], weights=w[m])) if m.any() else ''
            row[f'{g}_submerged_share'] = float(w[m & (z < 0)].sum() / w[m].sum()) if m.any() else ''
        rows.append(row)
    with open(ROOT / 'results/regional_elevation_history.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
