"""현대 대륙 모양에서 해성층 단면을 잠기게 하는 데 필요한 해수면을 단면의 지각 유형별로 나눈다 (devlog 014).

단면 유형: 단면 안 CRUST1.0 표본점 면적이 가장 큰 유형 묶음(crust_points.TYPE_GROUPS) —
선캄브리아 안정지괴(대륙 안쪽), 현생누대 조산대·호·열개대(나중에 솟은 곳 포함), 대륙연변(현재 대륙붕·사면).
시점마다 유형별로 해성 단위가 있는 단면 면적과, 그 단면들의 50%(면적 기준)를 잠기게 하는 해수면을 낸다.
출력: results/needed_sea_level_by_type.csv
"""
import collections
import csv

import numpy as np

from crust_points import ROOT, TYPE_GROUPS, dem_files, load_points
from independent_sea_level import modern_relief, read_curves
from macrostrat_compare import column_points, is_marine, load_macrostrat, weighted_quantile

REGIONS = {1: 'north_america', 8: 'south_america'}


def main():
    lon, lat, kind, thickness, area, volume = load_points()
    relief = np.repeat(modern_relief()[1], 4)
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
        threshold, col_type = {}, {}
        for c in np.unique(owner[owner >= 0]):
            m = owner == c
            threshold[c] = weighted_quantile(relief[m], area[m], 0.5)
            weights = collections.Counter()
            for g, a in zip(group[m], area[m]):
                weights[g] += a
            col_type[c] = weights.most_common(1)[0][0]
        for age in ages:
            marine = {u['col_id'] for u in units if u['t_age'] <= age <= u['b_age'] and is_marine(u)}
            row = {'region': region, 'age_ma': f'{age:g}', 'tect_avg_m': curves[int(round(age))]['tect'][0]}
            for name in TYPE_GROUPS:
                cols = [c for c in marine if c in threshold and col_type[c] == name]
                w = np.array([col_area[c] for c in cols])
                row[f'{name}_marine_area'] = w.sum() / 1e6
                row[f'{name}_needed_sea_level_m'] = (weighted_quantile(np.array([threshold[c] for c in cols]), w, 0.5)
                                                     if cols else '')
            rows.append(row)
        print(region, 'columns by type', collections.Counter(col_type.values()))
    with open(ROOT / 'results/needed_sea_level_by_type.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
