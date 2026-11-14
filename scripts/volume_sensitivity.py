"""부피 검사(devlog 011)의 민감도: 대륙이 등압평형이 아닌 이유(동적 지형 등)로 일정 높이만큼 눌려 있었다면 (devlog 015).

Scotese 고도에 Δ(0–400 m)를 더한 고도를 등압평형 고도로 보고 두께로 바꾼다. 곧 "Scotese가 그린 고도 = 등압평형 고도 − Δ"
(Δ는 동적 지형·열 상태 등으로 눌린 높이)라고 본다. 면적 정의는 겹침과 그때 없던 지괴를 뺀 셋째 정의다.
또 Δ = 0의 두께 부족을 PaleoDEM 칸 종류로 나눈다(banjang 2차 검토, B의 순환성): 그 지도의 단일값 칸(devlog 003),
그 밖의 물에 잠긴 칸(값 < 0), 육지 칸(값 ≥ 0). 기준 두께는 0 Ma 지도에서 같은 방법으로 낸 표본점별 두께다.
출력: results/volume_sensitivity.csv, results/thickness_deficit_by_cell_type.csv
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, dem_files, read_dem, sample
from crust_volume import calibration
from independent_sea_level import K

OFFSETS = (0, 100, 200, 250, 300, 400)


def main():
    fill = {}
    with open(ROOT / 'results/depth_classes_summary.csv') as f:
        for r in csv.DictReader(f):
            if r['resolution'] == '1deg':
                fill[round(float(r['age_ma']))] = int(r['fill_value_m']) if r['fill_value_m'] else None
    split_rows, point_reference = [], None
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
            point_reference = thick(dry)
        loss = w * (point_reference - thick(dry))
        base = float(np.sum(w * point_reference))
        value = fill.get(round(age))
        is_fill = (z == value) if value is not None else np.zeros(len(z), bool)
        split_rows.append({'age_ma': f'{age:g}', 'fill_value_m': '' if value is None else value,
                           'deficit_total': float(loss.sum()) / base,
                           'deficit_fill_cells': float(loss[is_fill].sum()) / base,
                           'deficit_other_submerged_cells': float(loss[(z < 0) & ~is_fill].sum()) / base,
                           'deficit_land_cells': float(loss[(z >= 0) & ~is_fill].sum()) / base,
                           'area_share_fill': float(w[is_fill].sum() / w.sum()),
                           'area_share_land': float(w[(z >= 0) & ~is_fill].sum() / w.sum())})
        row = {'age_ma': f'{age:g}', 'area_ratio': w.sum() / al.area.sum()}
        for d in OFFSETS:
            row[f'volume_ratio_offset_{d}'] = float(np.sum(w * thick(dry + d))) / reference
            row[f'thickness_ratio_offset_{d}'] = float(np.sum(w * thick(dry + d)) / w.sum()) / (reference / al.area.sum())
        rows.append(row)
    with open(ROOT / 'results/thickness_deficit_by_cell_type.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(split_rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in split_rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})
    with open(ROOT / 'results/volume_sensitivity.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
