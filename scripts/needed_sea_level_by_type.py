"""현대 대륙 모양에서 해성층 단면을 잠기게 하는 데 필요한 해수면을 단면의 지각 유형별로 나눈다 (devlog 014).

단면 유형: 단면 안 CRUST1.0 표본점 면적이 가장 큰 유형 묶음(crust_points.TYPE_GROUPS) —
선캄브리아 안정지괴(대륙 안쪽), 현생누대 조산대·호·열개대(나중에 솟은 곳 포함), 대륙연변(현재 대륙붕·사면).
시점마다 유형별로 해성 단위가 있는 단면 면적과, 그 단면들의 50%(면적 기준)를 잠기게 하는 해수면을 낸다.
안정지괴 단면은 더 나눈다(devlog 015, banjang 검토):
- 현재 잔차 지형(Stephenson et al. 2024, 1° 칸 평균, 지금 맨틀이 떠받치는 높이)을 현대 고도에서 뺀 "잔차 보정" 값.
  표본점이 든 1° 칸에 자료가 없으면 0으로 두고, 보정 자료가 있는 면적 비율을 함께 적는다.
- CRUST1.0 퇴적층 두께로 분지 단면(≥ 1 km)과 순상지 단면(< 0.5 km)을 나눈 값.
- 독립 해수면의 최소·최대(tect min/max)를 함께 적어 범위로 읽는다.
출력: results/needed_sea_level_by_type.csv
"""
import collections
import csv
import io
import tarfile
import zipfile

import numpy as np

from crust_points import INPUTS, OCEAN_OR_AMBIGUOUS, ROOT, TYPE_GROUPS, dem_files, load_points
from independent_sea_level import modern_relief, read_curves
from macrostrat_compare import column_points, is_marine, load_macrostrat, weighted_quantile

REGIONS = {1: 'north_america', 8: 'south_america'}


def residual_topography(lon, lat):
    """표본점마다 Stephenson et al. (2024) 1° 칸 평균 잔차 고도(m). 자료가 없으면 NaN."""
    with zipfile.ZipFile(INPUTS / 'residual/global-residual-topography-v1.0.1.zip') as z:
        name = [n for n in z.namelist() if n.endswith('binned_res_topo_1_deg.dat')][0]
        d = np.loadtxt(io.BytesIO(z.read(name)))
    blon = np.where(d[:, 0] > 180, d[:, 0] - 360, d[:, 0])
    key = {(int(np.floor(a)), int(np.floor(b))): v * 1000 for a, b, v in zip(blon, d[:, 1], d[:, 3])}
    return np.array([key.get((int(np.floor(a)), int(np.floor(b))), np.nan) for a, b in zip(lon, lat)])


def sediment_thickness():
    """CRUST1.0 대륙지각 셀의 퇴적층 두께(km), 표본점 순서(셀마다 네 번)."""
    with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as f:
        kind = np.loadtxt(f.extractfile('CNtype1-1.txt'), dtype=str).ravel()
    with tarfile.open(INPUTS / 'crust1.0.tar.gz') as f:
        bounds = np.loadtxt(f.extractfile('crust1.bnds'))
    layers = -np.diff(bounds[~np.isin(kind, OCEAN_OR_AMBIGUOUS)], axis=1)
    return np.repeat(layers[:, 2:5].sum(axis=1), 4)


def main():
    lon, lat, kind, thickness, area, volume = load_points()
    relief = np.repeat(modern_relief()[1], 4)
    residual = residual_topography(lon, lat)
    corrected = relief - np.nan_to_num(residual)
    sediment = sediment_thickness()
    curves = read_curves()
    group = np.full(len(kind), '', dtype=object)
    for name, kinds in TYPE_GROUPS.items():
        group[np.isin(kind, kinds)] = name
    ages = sorted(a for _, a, _ in dem_files('dem.zip'))
    rows = []
    for project, region in REGIONS.items():
        units, columns = load_macrostrat(project)
        owner = column_points(columns, lon, lat)
        col_area = {f['properties']['col_id']: float(f['properties']['col_area']) for f in columns}
        threshold, col_type, threshold_corr, coverage, col_sed = {}, {}, {}, {}, {}
        for c in np.unique(owner[owner >= 0]):
            m = owner == c
            threshold[c] = weighted_quantile(relief[m], area[m], 0.5)
            threshold_corr[c] = weighted_quantile(corrected[m], area[m], 0.5)
            coverage[c] = area[m & np.isfinite(residual)].sum() / area[m].sum()
            col_sed[c] = weighted_quantile(sediment[m], area[m], 0.5)
            weights = collections.Counter()
            for g, a in zip(group[m], area[m]):
                weights[g] += a
            col_type[c] = weights.most_common(1)[0][0]
        for age in ages:
            marine = {u['col_id'] for u in units if u['t_age'] <= age <= u['b_age'] and is_marine(u)}
            tect = curves[int(round(age))]['tect']
            row = {'region': region, 'age_ma': f'{age:g}', 'tect_avg_m': tect[0], 'tect_min_m': min(tect), 'tect_max_m': max(tect)}
            for name in TYPE_GROUPS:
                cols = [c for c in marine if c in threshold and col_type[c] == name]
                w = np.array([col_area[c] for c in cols])
                row[f'{name}_marine_area'] = w.sum() / 1e6
                row[f'{name}_needed_sea_level_m'] = (weighted_quantile(np.array([threshold[c] for c in cols]), w, 0.5)
                                                     if cols else '')
            craton = [c for c in marine if c in threshold and col_type[c] == 'precambrian_craton']
            for label, cols in (('craton_residual_corrected', craton),
                                ('craton_basin', [c for c in craton if col_sed[c] >= 1.0]),
                                ('craton_shield', [c for c in craton if col_sed[c] < 0.5])):
                w = np.array([col_area[c] for c in cols])
                table = threshold_corr if label == 'craton_residual_corrected' else threshold
                row[f'{label}_marine_area'] = w.sum() / 1e6
                row[f'{label}_needed_sea_level_m'] = (weighted_quantile(np.array([table[c] for c in cols]), w, 0.5)
                                                      if cols else '')
            w = np.array([col_area[c] for c in craton])
            row['craton_residual_coverage'] = float(np.average([coverage[c] for c in craton], weights=w)) if craton else ''
            rows.append(row)
        print(region, 'columns by type', collections.Counter(col_type.values()),
              'craton basin/shield', sum(1 for c in col_type if col_type[c] == 'precambrian_craton' and col_sed[c] >= 1.0),
              sum(1 for c in col_type if col_type[c] == 'precambrian_craton' and col_sed[c] < 0.5))
    with open(ROOT / 'results/needed_sea_level_by_type.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
