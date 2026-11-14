"""부피 부족(devlog 011)이 어느 지역에서 오는지 판 번호 첫 자리 묶음별로 나눈다 (devlog 013).

표본점마다 기준 두께 = 0 Ma 지도에서 같은 방법(crust_volume.py의 고도 → 두께 보간)으로 낸 두께.
시점마다 묶음별로
- 기준 부피 = Σ 표본점 면적 × 기준 두께
- 면적 몫 = Σ (표본점 면적 − 남은 면적) × 기준 두께. 남은 면적은 판 겹침을 셀 면적에 맞게 줄이고 그때 없던 지괴
  (물가 아래 1,400 m보다 깊고 얕은 곳에서 3°보다 멂)와 미해결 점을 뺀 면적이다.
- 두께 몫 = Σ 남은 면적 × (기준 두께 − 그 시점 Scotese 고도로 낸 두께)
기준 부피 − 면적 몫 − 두께 몫 = 그 시점 Scotese 지형이 담는 부피.
출력: results/crust_volume_by_region.csv (단위 백만 km³)
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, dem_files, read_dem, sample
from crust_volume import calibration
from independent_sea_level import K

GROUPS = {1: '북미', 2: '남미', 3: '유럽', 4: '북아시아', 5: '남·서아시아', 6: '동아시아', 7: '아프리카', 8: '남극·호주'}


def main():
    centres, means, _ = calibration()
    thick = lambda d: np.interp(d, centres, means)
    first = np.array([int(str(p)[0]) if p >= 0 else 0 for p in al.plates.plate_id])
    group = np.where(np.isin(first, list(GROUPS)), first, 9)
    files = sorted(dem_files('dem.zip'), key=lambda r: r[1])
    reference = None
    rows = []
    for map_no, age, name in files:
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        dry = np.nan_to_num(np.where(z < 0, z * K, z))
        _, _, factor = al.coverage(plat, plon, valid)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        t_now = thick(dry)
        if reference is None:
            reference = t_now.copy()          # 0 Ma
        kept = np.where(valid & ~far, al.area * factor, 0.0)
        for g in list(GROUPS) + [9]:
            m = group == g
            ref = np.sum(al.area[m] * reference[m]) / 1e6
            area_loss = np.sum((al.area[m] - kept[m]) * reference[m]) / 1e6
            thick_loss = np.sum(kept[m] * (reference[m] - t_now[m])) / 1e6
            rows.append({'age_ma': f'{age:g}', 'group': g, 'region': GROUPS.get(g, '기타'),
                         'area': al.area[m].sum() / 1e6, 'kept_area': kept[m].sum() / 1e6,
                         'far_area': al.area[m & far].sum() / 1e6,
                         'reference_volume': ref, 'area_loss': area_loss, 'thickness_loss': thick_loss,
                         'scotese_volume': ref - area_loss - thick_loss,
                         'mean_dry_kept_m': float(np.average(dry[m], weights=kept[m])) if kept[m].sum() else 0.0,
                         'mean_dry_reference_m': float(np.average(np.nan_to_num(sample(read_dem('dem.zip', files[0][2], (181, 361)), al.lat[m], al.lon[m], 1.0)), weights=al.area[m])) if age == 0 else ''})
    with open(ROOT / 'results/crust_volume_by_region.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
