"""웹 페이지(web/)가 읽는 자료를 results/와 원자료에서 만든다 (devlog 007).

출력: web/data/ (git에 올리지 않는다)
- summary.json: 시점 목록과 단계별 시계열·표
- hist.json: 0.1° 격자의 시점별 값(−480 ~ +200 m) 면적
- dem/<나이>.bin: PaleoDEM 0.5°(0.1° 격자의 점 표본) int16, 361 × 721, 위도 90 → −90, 경도 −180 → 180
- crust_sea_level_0.bin, crust_atlas.bin: 시점 × 181 × 360 uint8, 1° 고격자의 대륙지각 상태
  (0 없음, 1 육지, 2 잠김, 3 깊음(물가 아래 1,400 m보다), 4 깊음이고 얕은 곳에서 3°보다 멂; +8 판 겹침)
- macrostrat.json: 북미 단면 다각형(현대 위치)과 시점별 기록·모델 상태
"""
import collections
import csv
import json
from pathlib import Path

import numpy as np

import alignment as al
from crust_points import ROOT, atlas_levels, dem_files, read_dem, sample
from macrostrat_compare import column_points, is_marine, load_macrostrat

OUT = ROOT / 'web' / 'data'
DEEP = 1400


def read_csv(name):
    with open(ROOT / 'results' / name) as f:
        return list(csv.DictReader(f))


def num(v):
    return None if v in ('', None) else round(float(v), 4)


def crust_codes(z, level, g1, plat, plon, valid, factor):
    """1° 고격자 셀마다 점 면적이 가장 큰 상태."""
    area = al.area
    state = np.zeros(len(z), int)
    state[valid & (z >= level)] = 1
    state[valid & (z < level)] = 2
    deep = valid & (z < level - DEEP)
    state[deep] = 3
    iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
    dist = al.distance_class(g1[:, :360] >= level - 200, iy, ix)
    state[deep & (dist == 99)] = 4
    flat = (iy * 360 + ix)[valid]
    weights = np.zeros((5, 181 * 360))
    for s in range(1, 5):
        m = state[valid] == s
        weights[s] = np.bincount(flat[m], weights=area[valid][m], minlength=181 * 360)
    # 깊은 곳(3, 4)을 합쳐 다른 상태와 비교하고, 그 안에서 멂(4)이 절반을 넘으면 4로 둔다.
    merged = weights[[0, 1, 2]].copy()
    merged = np.vstack([merged, weights[3] + weights[4]])
    code = merged.argmax(axis=0)
    code[(code == 3) & (weights[4] > weights[3])] = 4
    code[merged.sum(axis=0) == 0] = 0
    overlap = np.zeros(181 * 360, bool)
    overlap[flat[factor[valid] < 1]] = True
    code = code + 8 * (overlap & (code > 0))
    return code.astype(np.uint8)


def main():
    (OUT / 'dem').mkdir(parents=True, exist_ok=True)
    atlas = atlas_levels()
    files_1 = sorted(dem_files('dem.zip'), key=lambda r: r[1])
    files_6 = {round(a): n for m, a, n in dem_files('dem_6min.zip')}
    classes = {round(float(r['age_ma'])): r for r in read_csv('depth_classes_summary.csv') if r['resolution'] == '6min'}
    waterline = collections.defaultdict(list)
    for r in read_csv('PALEOMAP_CRUST1_waterline_0-540Ma.csv'):
        waterline[r['age_ma']].append(r)
    align = {r['age_ma']: r for r in read_csv('alignment_summary.csv')}
    macro = {r['age_ma']: r for r in read_csv('macrostrat_north_america.csv')}
    macro_sa = {r['age_ma']: r for r in read_csv('macrostrat_south_america.csv')}
    indep = {r['age_ma']: r for r in read_csv('independent_sea_level.csv')}
    margin = {r['age_ma']: r for r in read_csv('margin_length.csv')}
    volume = {r['age_ma']: r for r in read_csv('crust_volume.csv')}
    v0 = volume['0']
    a0 = float(v0['dedup_without_far_area'])
    t0 = float(v0['dedup_without_far_volume']) * 1e9 / (a0 * 1e6)

    units, columns = load_macrostrat()
    col_ids = [f['properties']['col_id'] for f in columns]
    owner = column_points(columns, al.lon, al.lat)
    index = {c: i for i, c in enumerate(col_ids)}
    owner_index = np.array([index.get(c, -1) for c in owner])

    ages, crust_0, crust_a, macro_codes = [], [], [], []
    for map_no, age, name in files_1:
        key = f'{age:g}'
        g1 = read_dem('dem.zip', name, (181, 361))
        g6 = read_dem('dem_6min.zip', files_6[round(age)], (1801, 3601))
        g6[::5, ::5].astype('<i2').tofile(OUT / 'dem' / f'{key}.bin')
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        z1 = sample(g1, plat, plon, 1.0)
        _, _, factor = al.coverage(plat, plon, valid)
        levels = sorted({a['level'] for a in atlas.get(map_no, [])})
        crust_0.append(crust_codes(z1, 0, g1, plat, plon, valid, factor))
        crust_a.append(crust_codes(z1, max(levels), g1, plat, plon, valid, factor) if levels else crust_0[-1])
        # Macrostrat 단면 상태: 기록(0 없음, 1 비해성만, 2 해성) × 모델(0 안 잠김, 1 잠김), 점이 없는 단면은 9.
        spans = [u for u in units if u['t_age'] <= age <= u['b_age']]
        any_cols = {u['col_id'] for u in spans}
        marine_cols = {u['col_id'] for u in spans if is_marine(u)}
        inside = (owner_index >= 0) & np.isfinite(z1)
        level = max(levels) if levels else 0
        wet = np.bincount(owner_index[inside], weights=al.area[inside] * (z1[inside] < level), minlength=len(col_ids))
        tot = np.bincount(owner_index[inside], weights=al.area[inside], minlength=len(col_ids))
        codes = []
        for i, c in enumerate(col_ids):
            if tot[i] == 0:
                codes.append('9')
                continue
            record = 2 if c in marine_cols else (1 if c in any_cols else 0)
            codes.append(str(record * 2 + int(wet[i] > tot[i] / 2)))
        macro_codes.append(''.join(codes))
        c6 = classes[round(age)]
        wl = waterline[key]
        zero = [r for r in wl if r['waterline'] == 'sea_level_0'][0]
        atl = [r for r in wl if r['waterline'] == 'atlas']
        a = align[key]
        m = macro[key]
        ages.append({
            'age': age, 'map': map_no, 'history_age': num(c6['history_age_ma']), 'phase': c6['phase'],
            'atlas': atlas.get(map_no, []),
            'fill_value': None if c6['fill_value_m'] == '' else int(c6['fill_value_m']),
            'fill_ratio': num(c6['fill_ratio']), 'fill_area': num(c6['fill_area']),
            'shallow_0_200': num(c6['shallow_0_to_200m']), 'shallow_with_fill': num(c6['shallow_with_fill']),
            'sub_sl0': num(zero['submerged_million_km2']),
            'sub_atlas_min': min((num(r['submerged_million_km2']) for r in atl), default=None),
            'sub_atlas_max': max((num(r['submerged_million_km2']) for r in atl), default=None),
            'sub_atlas_max_incl': max((num(float(r['submerged_million_km2']) + float(r['at_waterline_million_km2'])) for r in atl), default=None),
            'dedup_sl0': num(a['dedup_submerged_sea_level_0']), 'dedup_atlas_max': num(a['dedup_submerged_atlas_max']),
            'deep': num(a['deep_1deg']), 'deep_margin': num(a['deep_margin']),
            'deep_craton': num(a['deep_precambrian_craton']), 'deep_orogen': num(a['deep_phanerozoic_orogen_arc_rift']),
            'deep_far': num(a['deep_farther_than_3deg']), 'overlap': num(a['plate_overlap']),
            'dem_without_crust': num(a['dem_continent_without_crust']),
            'craton_on_continent': num(a['craton_on_continent_share']),
            'macro_marine': num(m['macrostrat_marine']), 'macro_marine_nopbdb': num(m['macrostrat_marine_without_pbdb_units']),
            'macro_any': num(m['macrostrat_any_units']), 'model_na_atlas_max': num(m['model_submerged_atlas_max']),
            'model_na_sl0': num(m['model_submerged_sea_level_0']),
            'model_na_modern': num(m['modern_shape_submerged_tect_avg']),
            'na_needed_sl': num(m['modern_shape_sea_level_for_half_of_marine_columns_m']),
            'sa_marine': num(macro_sa[key]['macrostrat_marine']), 'sa_atlas_max': num(macro_sa[key]['model_submerged_atlas_max']),
            'sa_modern': num(macro_sa[key]['modern_shape_submerged_tect_avg']),
            'sa_needed_sl': num(macro_sa[key]['modern_shape_sea_level_for_half_of_marine_columns_m']),
            **{k: num(indep[key][k]) for k in ('tect_avg_m', 'tect_min_m', 'tect_max_m', 'tge_avg_m', 'A_tect_avg', 'A_band_tect_avg',
                                               'B_tect_avg', 'B_band_tect_avg', 'B_band_tect_min', 'B_band_tect_max', 'A_band_tge_avg', 'B_band_tge_avg')},
            **{k: num(margin[key][k]) for k in ('margin_ratio', 'margin_without_far_ratio', 'shelf_harris_width', 'shelf_harris_width_without_far')},
            **{k: num(volume[key][k]) for k in ('tracked_volume_ratio', 'dedup_volume_ratio', 'dedup_without_far_volume_ratio', 'dedup_without_far_mean_dry_m')},
            'volume_area_ratio': num(float(volume[key]['dedup_without_far_area']) / a0),
            'volume_thickness_ratio': num(float(volume[key]['dedup_without_far_volume']) * 1e9 / (float(volume[key]['dedup_without_far_area']) * 1e6) / t0),
        })
        print(key, flush=True)
    np.stack(crust_0).tofile(OUT / 'crust_sea_level_0.bin')
    np.stack(crust_a).tofile(OUT / 'crust_atlas.bin')

    hist = collections.defaultdict(dict)
    for r in read_csv('depth_classes.csv'):
        v = int(r['value_m'])
        if r['resolution'] == '6min' and -480 <= v <= 200:
            hist[r['age_ma']][v] = round(float(r['area_million_km2']), 4)
    json.dump(hist, open(OUT / 'hist.json', 'w'), separators=(',', ':'))

    shift = collections.defaultdict(dict)
    for r in read_csv('alignment_age_shift.csv'):
        shift[r['age_ma']][r['shift_myr']] = [num(r['elevation_correlation']), num(r['craton_on_continent_share'])]
    plates = [r for r in read_csv('alignment_plates.csv') if r['age_ma'] == '500']
    plates = sorted(plates, key=lambda r: -float(r['deep_farther_than_3deg']))[:10]
    map_age = {m: a for m, a, n in files_1}
    check = [{'age': map_age[r['matched_dem_map']], 'atlas_map': r['atlas_map'], 'dem_map': r['matched_dem_map'],
              'caption': int(r['caption_sea_level_m']), 'best': int(r['best_sea_level_m']),
              'agree_caption': num(r['agreement_caption']), 'agree_incl': num(r[f"agree_{int(r['caption_sea_level_m']) + 40}"]),
              'agree_best': num(r['agreement_best']), 'rival': r['best_rival_map'], 'agree_rival': num(r['agreement_best_rival'])}
             for r in read_csv('atlas_sea_level_check.csv')]
    json.dump({'ages': ages, 'age_shift': shift, 'atlas_check': check,
               'plates_500': [{k: (num(v) if k not in ('main_types', 'plate_id') else v) for k, v in r.items()} for r in plates]},
              open(OUT / 'summary.json', 'w'), separators=(',', ':'), ensure_ascii=False)

    polys = []
    for f in columns:
        g = f['geometry']
        rings = [g['coordinates'][0]] if g['type'] == 'Polygon' else [p[0] for p in g['coordinates']]
        polys.append([[[round(x, 2), round(y, 2)] for x, y in ring] for ring in rings])
    json.dump({'col_ids': col_ids, 'polygons': polys, 'codes': macro_codes},
              open(OUT / 'macrostrat.json', 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
