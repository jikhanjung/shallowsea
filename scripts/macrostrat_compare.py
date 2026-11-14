"""Macrostrat 단면의 해성층 기록과, 같은 범위의 모델 잠김(CRUST1.0 + PALEOMAP + PaleoDEM)을 비교한다 (devlog 006, 012).

사용: python scripts/macrostrat_compare.py [프로젝트 번호]   (1 = 북미, 기본값; 8 = 남미)

Macrostrat은 보존된 지층의 기록이다. 해성층이 없으면 침수되지 않았거나, 퇴적되지 않았거나, 침식된 것이다.
그러므로 "해성층이 있다"는 침수의 하한이고, "없다"는 침수가 없었다는 뜻이 아니다.

출력
- results/macrostrat_<지역>.csv: 109개 시점마다 Macrostrat 해성층 단면 면적과 모델 잠김 면적. 모델은 Scotese 지형에
  아틀라스 해수면·해수면 0·독립 해수면(van der Meer et al. 2022 판구조 평균)을 넣은 것과, 현대 대륙 모양을 고정하고
  독립 해수면을 넣은 것(모델 B, Scotese 자료를 쓰지 않음)이다.
- results/macrostrat_<지역>_agreement.csv: 시점마다 단면 단위 일치표 (북미는 예전 이름 macrostrat_columns_agreement.csv)
"""
import csv
import json
import sys

import numpy as np
import pygplates as pg

from crust_points import INPUTS, ROOT, Plates, atlas_levels, dem_files, load_points, read_dem, sample

MACRO = INPUTS / 'macrostrat'
OUTPUTS = {1: ('macrostrat_north_america.csv', 'macrostrat_columns_agreement.csv'),
           8: ('macrostrat_south_america.csv', 'macrostrat_south_america_agreement.csv')}


def load_macrostrat(project=1):
    units = json.load(open(MACRO / f'units_project{project}.json'))['success']['data']
    columns = json.load(open(MACRO / f'columns_project{project}.geojson'))['features']
    return units, columns


def is_marine(unit):
    return any(e['class'] == 'marine' for e in unit['environ'])


def column_points(columns, lon, lat):
    """현대 위치가 단면 다각형 안에 드는 CRUST1.0 표본점의 단면 번호. 없으면 −1."""
    owner = np.full(len(lon), -1)
    for feature in columns:
        geometry = feature['geometry']
        rings = [geometry['coordinates'][0]] if geometry['type'] == 'Polygon' else [p[0] for p in geometry['coordinates']]
        for ring in rings:
            ring = np.asarray(ring)
            box = ((lon >= ring[:, 0].min()) & (lon <= ring[:, 0].max()) &
                   (lat >= ring[:, 1].min()) & (lat <= ring[:, 1].max()) & (owner < 0))
            if not box.any():
                continue
            polygon = pg.PolygonOnSphere([(float(y), float(x)) for x, y in ring])
            for i in np.flatnonzero(box):
                if polygon.is_point_in_polygon(pg.PointOnSphere(float(lat[i]), float(lon[i]))):
                    owner[i] = feature['properties']['col_id']
    return owner


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    cum = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][min(np.searchsorted(cum, q), len(values) - 1)])


def ranks(x):
    order = np.argsort(x)
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    return r


def main(project=1):
    from independent_sea_level import modern_relief, read_curves
    curves = read_curves()
    units, columns = load_macrostrat(project)
    col_area = {f['properties']['col_id']: float(f['properties']['col_area']) for f in columns}
    lon, lat, kind, thickness, area, volume = load_points()
    owner = column_points(columns, lon, lat)
    inside = owner >= 0
    # 모델 B: 표본점은 CRUST1.0 셀마다 네 개씩 같은 순서로 놓여 있으므로 셀의 현대 dry 고도를 네 번 되풀이한다.
    relief = np.repeat(modern_relief()[1], 4)
    assert len(relief) == len(lon)
    # 단면마다 현대 dry 고도의 면적 가중 중앙값. 해수면이 이보다 높으면 현대 모양에서 그 단면의 절반 넘게가 잠긴다.
    col_threshold = {}
    for c in np.unique(owner[inside]):
        m = owner == c
        col_threshold[c] = weighted_quantile(relief[m], area[m], 0.5)
    plates = Plates(lon, lat)
    atlas = {m: [a['level'] for a in v] for m, v in atlas_levels().items()}
    col_ids = np.array(sorted(col_area))
    index = {c: i for i, c in enumerate(col_ids)}
    owner_index = np.array([index.get(c, -1) for c in owner])
    rows, agreement = [], []
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        spans = [u for u in units if u['t_age'] <= age <= u['b_age']]
        any_cols = {u['col_id'] for u in spans}
        marine_cols = {u['col_id'] for u in spans if is_marine(u)}
        marine_nopbdb = {u['col_id'] for u in spans if is_marine(u) and u['pbdb_collections'] == 0}
        plat, plon = plates.paleo(age)
        z = sample(read_dem('dem.zip', name, (181, 361)), plat, plon, 1.0)
        valid = inside & np.isfinite(z)
        levels = atlas.get(map_no, [])
        row = {
            'age_ma': f'{age:g}', 'map': map_no,
            'macrostrat_any_units': sum(col_area[c] for c in any_cols) / 1e6,
            'macrostrat_marine': sum(col_area[c] for c in marine_cols) / 1e6,
            'macrostrat_marine_without_pbdb_units': sum(col_area[c] for c in marine_nopbdb) / 1e6,
            'model_footprint': area[valid].sum() / 1e6,
            'model_submerged_sea_level_0': area[valid & (z < 0)].sum() / 1e6,
            'model_submerged_atlas_min': area[valid & (z < min(levels))].sum() / 1e6 if levels else '',
            'model_submerged_atlas_max': area[valid & (z < max(levels))].sum() / 1e6 if levels else '',
            'model_submerged_tect_avg': area[valid & (z < curves[int(round(age))]['tect'][0])].sum() / 1e6,
            'modern_shape_submerged_tect_avg': area[inside & (relief < curves[int(round(age))]['tect'][0])].sum() / 1e6,
            'tect_avg_m': curves[int(round(age))]['tect'][0],
        }
        # 현대 모양에서 해성층 단면(면적 기준)의 50%·80%를 잠기게 하려면 해수면이 얼마여야 하는가.
        marine_with_points = [c for c in marine_cols if c in col_threshold]
        if marine_with_points:
            v = np.array([col_threshold[c] for c in marine_with_points])
            w = np.array([col_area[c] for c in marine_with_points])
            row['modern_shape_sea_level_for_half_of_marine_columns_m'] = weighted_quantile(v, w, 0.5)
            row['modern_shape_sea_level_for_80pct_of_marine_columns_m'] = weighted_quantile(v, w, 0.8)
        else:
            row['modern_shape_sea_level_for_half_of_marine_columns_m'] = ''
            row['modern_shape_sea_level_for_80pct_of_marine_columns_m'] = ''
        rows.append(row)
        # 단면 단위 일치: 단면 안 표본점 면적의 절반 넘게 잠기면 모델에서 잠긴 단면으로 본다.
        level = max(levels) if levels else 0
        wet = np.bincount(owner_index[valid], weights=area[valid] * (z[valid] < level), minlength=len(col_ids))
        tot = np.bincount(owner_index[valid], weights=area[valid], minlength=len(col_ids))
        has = tot > 0
        model_wet = has & (wet > tot / 2)
        recorded = np.isin(col_ids, list(any_cols)) & has
        marine = np.isin(col_ids, list(marine_cols)) & has
        a = np.array([col_area[c] for c in col_ids]) / 1e6
        agreement.append({
            'age_ma': f'{age:g}', 'waterline': 'atlas_max' if levels else 'sea_level_0', 'sea_level_m': level,
            'columns_with_points': int(has.sum()), 'columns_with_record': int(recorded.sum()),
            'marine_and_model_wet': a[marine & model_wet].sum(), 'marine_and_model_dry': a[marine & ~model_wet].sum(),
            'nonmarine_record_and_model_wet': a[recorded & ~marine & model_wet].sum(),
            'nonmarine_record_and_model_dry': a[recorded & ~marine & ~model_wet].sum(),
            'no_record_and_model_wet': a[has & ~recorded & model_wet].sum(),
            'no_record_and_model_dry': a[has & ~recorded & ~model_wet].sum(),
        })
    for path, out in zip(OUTPUTS[project], (rows, agreement)):
        with open(ROOT / 'results' / path, 'w', newline='') as f:
            writer = csv.DictWriter(f, list(out[0]), lineterminator='\n')
            writer.writeheader()
            for r in out:
                writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})
    with_atlas = [r for r in rows if r['model_submerged_atlas_max'] != '']
    m = np.array([r['macrostrat_marine'] for r in with_atlas])
    s = np.array([r['model_submerged_atlas_max'] for r in with_atlas])
    print('Spearman (atlas max, n=%d): %.3f' % (len(m), np.corrcoef(ranks(m), ranks(s))[0, 1]))
    m = np.array([r['macrostrat_marine'] for r in rows])
    for key in ('model_submerged_tect_avg', 'modern_shape_submerged_tect_avg'):
        s = np.array([r[key] for r in rows])
        print('Spearman (%s, n=%d): %.3f' % (key, len(m), np.corrcoef(ranks(m), ranks(s))[0, 1]))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
