"""Macrostrat 북미 단면의 해성층 기록과, 같은 범위의 모델 잠김(CRUST1.0 + PALEOMAP + PaleoDEM)을 비교한다 (devlog 006).

Macrostrat은 보존된 지층의 기록이다. 해성층이 없으면 침수되지 않았거나, 퇴적되지 않았거나, 침식된 것이다.
그러므로 "해성층이 있다"는 침수의 하한이고, "없다"는 침수가 없었다는 뜻이 아니다.

출력
- results/macrostrat_north_america.csv: 109개 시점마다 Macrostrat 해성층 단면 면적과 모델 잠김 면적
- results/macrostrat_columns_agreement.csv: 시점마다 단면 단위 일치표
"""
import csv
import json

import numpy as np
import pygplates as pg

from crust_points import INPUTS, ROOT, Plates, dem_files, load_points, read_dem, sample

MACRO = INPUTS / 'macrostrat'


def load_macrostrat():
    units = json.load(open(MACRO / 'units_project1.json'))['success']['data']
    columns = json.load(open(MACRO / 'columns_project1.geojson'))['features']
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


def ranks(x):
    order = np.argsort(x)
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    return r


def main():
    units, columns = load_macrostrat()
    col_area = {f['properties']['col_id']: float(f['properties']['col_area']) for f in columns}
    lon, lat, kind, thickness, area, volume = load_points()
    owner = column_points(columns, lon, lat)
    inside = owner >= 0
    plates = Plates(lon, lat)
    atlas = {}
    with open(ROOT / 'docs/paleoatlas_sea_levels.csv') as f:
        for r in csv.DictReader(f):
            atlas.setdefault(r['atlas_map'], []).append(int(r['sea_level_m']))
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
        }
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
    for path, out in (('macrostrat_north_america.csv', rows), ('macrostrat_columns_agreement.csv', agreement)):
        with open(ROOT / 'results' / path, 'w', newline='') as f:
            writer = csv.DictWriter(f, list(out[0]), lineterminator='\n')
            writer.writeheader()
            for r in out:
                writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})
    with_atlas = [r for r in rows if r['model_submerged_atlas_max'] != '']
    m = np.array([r['macrostrat_marine'] for r in with_atlas])
    s = np.array([r['model_submerged_atlas_max'] for r in with_atlas])
    print('Spearman (atlas max, n=%d): %.3f' % (len(m), np.corrcoef(ranks(m), ranks(s))[0, 1]))


if __name__ == '__main__':
    main()
