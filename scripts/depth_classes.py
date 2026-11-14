"""PaleoDEM 1°·0.1° 배포본의 얕은 바다 수심값별 면적을 지도마다 집계한다 (devlog 003).

출력
- results/depth_classes.csv: 해상도·지도·값(−1,400 ~ +400 m)별 구면 면적
- results/depth_classes_summary.csv: 지도별 요약(40 m 격자 밖 면적, 해수면 부근 단일값 쏠림,
  1°와 0.1° 격자점 일치율)
"""
import csv
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'inputs'
RADIUS = 6371.0088
SHALLOW_FLOOR = -1400
CEILING = 400
# 해수면 부근에서 이웃 두 값 평균의 몇 배 넘게 몰린 값을 단일값 쏠림으로 본다.
FILL_RATIO = 3
STEP = 40
# Scotese & Wright (2018) 보고서 Table 1에서 굵은 글씨(Phase I, 2003–2008에 처음 만든 지도)인 0–540 Ma 시점.
# PDF 글꼴 정보에서 뽑았다(devlog 003). 나머지는 Phase II(2010–2013)의 보간 지도다.
PHASE_I = {0, 10, 20, 30, 40, 50, 55, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180,
           190, 200, 220, 240, 250, 260, 280, 300, 320, 340, 360, 380, 400, 420, 430, 440, 460,
           480, 500, 520, 540}
NAME = re.compile(r'(?:^|/)Map([\d.]+)_PALEOMAP_(?:1deg|6min)_.*?_([\d.]+)Ma\.nc$')
HISTORY_AGE = re.compile(r'_([\d.]+)Ma\.nc ')


def cell_area(n_lat, n_lon, step):
    """격자점 등록(gridline) 격자의 구면 셀 면적(km²). 극은 자르고 ±180° 중복 열은 반씩 센다."""
    lat = np.linspace(90, -90, n_lat)
    bounds = np.deg2rad(np.clip(np.stack([lat - step / 2, lat + step / 2]), -90, 90))
    area = RADIUS**2 * np.deg2rad(step) * np.diff(np.sin(bounds), axis=0)[0]
    area = np.repeat(area[:, None], n_lon, axis=1)
    area[:, [0, -1]] *= .5
    assert np.isclose(area.sum(), 4 * np.pi * RADIUS**2)
    return area


def read_grids(archive_path, shape):
    """zip 안의 PaleoDEM을 지도 번호 순으로 (지도 번호, 파일 나이, history 나이, 격자)로 돌려준다."""
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory() as tmp:
        names = [n for n in archive.namelist()
                 if NAME.search(n) and not Path(n).name.startswith('._')]
        for name in sorted(names, key=lambda n: float(NAME.search(n)[1])):
            map_no, age = NAME.search(name).groups()
            source = Path(tmp) / 'grid.nc'
            source.write_bytes(archive.read(name))
            info = subprocess.check_output(['gdalinfo', str(source)], text=True)
            match = HISTORY_AGE.search(info)
            raw = Path(tmp) / 'grid.bin'
            subprocess.check_call(['gdal_translate', '-q', '-of', 'ENVI', str(source), str(raw)])
            grid = np.fromfile(raw, dtype=np.float32).reshape(shape)
            assert np.isfinite(grid).all()
            yield map_no, float(age), (float(match[1]) if match else None), grid


def summarize(grid, area):
    """얕은 바다 수심값별 면적(백만 km²)과 요약값."""
    z = np.round(grid).astype(int)
    near = (z <= CEILING) & (z >= SHALLOW_FLOOR)
    values, index = np.unique(z[near], return_inverse=True)
    by_value = dict(zip(values.tolist(), np.bincount(index, weights=area[near]) / 1e6))
    shallow = near & (z <= 0)
    at = lambda v: by_value.get(v, 0.0)
    off_grid = (shallow & (grid % STEP != 0)).astype(float)
    # 0 m를 포함한 0 ~ −200 m에서 면적이 가장 많은 값. 지도마다 대륙내해를 한 값으로 칠한 흔적을 찾는다.
    band = {v: a for v, a in by_value.items() if -200 <= v <= 0}
    mode = max(band, key=band.get)
    # −200 ~ +80 m에서 이웃 두 값(±40 m) 평균에 비해 가장 많이 몰린 값.
    ratio = {v: at(v) / ((at(v - STEP) + at(v + STEP)) / 2) for v in range(-200, 81, STEP)}
    fill = max(ratio, key=ratio.get)
    has_fill = ratio[fill] >= FILL_RATIO
    summary = {
        'sea_level_0m': at(0),
        **{f'at_{d}m': at(-d) for d in (40, 80, 120, 160, 200, 240)},
        'shallow_0_to_200m': area[(z < 0) & (z >= -200)].sum() / 1e6,
        'with_0m_to_200m': area[(z <= 0) & (z >= -200)].sum() / 1e6,
        'mode_0_to_200m': mode,
        'mode_share': band[mode] / sum(band.values()),
        'off_40m_grid': (area * off_grid).sum() / 1e6,
        'spike_160m': ratio[-160],
        'fill_value_m': fill if has_fill else None,
        'fill_ratio': ratio[fill],
        'fill_area': at(fill) if has_fill else 0.0,
        'fill_excess': at(fill) - (at(fill - STEP) + at(fill + STEP)) / 2 if has_fill else 0.0,
        # 단일값이 해수면 이상(0, +40 m)에 칠해진 지도에서도 같은 지도 단위를 바다로 센 면적.
        'shallow_with_fill': area[(z < 0) & (z >= -200)].sum() / 1e6 + (at(fill) if has_fill and fill >= 0 else 0.0),
    }
    return by_value, summary


def main():
    area_1 = cell_area(181, 361, 1.0)
    area_6 = cell_area(1801, 3601, 0.1)
    one_degree = {}
    rows, summaries = [], []
    for map_no, age, history_age, grid in read_grids(INPUTS / 'dem.zip', (181, 361)):
        one_degree[round(age)] = (map_no, grid, history_age)
        by_value, summary = summarize(grid, area_1)
        rows += [('1deg', map_no, age, v, a) for v, a in by_value.items()]
        summaries.append({'resolution': '1deg', 'map': map_no, 'age_ma': age, 'history_age_ma': history_age,
                          'phase': 'I' if age in PHASE_I and '.' not in map_no else 'II', **summary})
    for map_no, age, _, grid in read_grids(INPUTS / 'dem_6min.zip', (1801, 3601)):
        by_value, summary = summarize(grid, area_6)
        rows += [('6min', map_no, age, v, a) for v, a in by_value.items()]
        # 280·285 Ma는 두 배포본의 지도 번호가 엇갈려(1°: 54·54.5, 0.1°: 53.5·54) 나이로 짝짓는다.
        coarse_map, coarse, history_age = one_degree.pop(round(age))
        # 1°의 북극 행(평균값)과 +180° 열(−180° 열 복사)을 빼고 같은 격자점끼리 비교한다.
        interior = (grid[::10, ::10] == coarse)[1:, :-1]
        summaries.append({'resolution': '6min', 'map': map_no, 'age_ma': age, 'history_age_ma': history_age,
                          'phase': 'I' if age in PHASE_I and '.' not in coarse_map else 'II', **summary,
                          'match_1deg_nodes': interior.mean()})
    assert not one_degree and len(summaries) == 218

    with open(ROOT / 'results/depth_classes.csv', 'w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['resolution', 'map', 'age_ma', 'value_m', 'area_million_km2'])
        writer.writerows([r, m, f'{a:g}', v, f'{x:.5f}'] for r, m, a, v, x in rows)
    with open(ROOT / 'results/depth_classes_summary.csv', 'w', newline='') as f:
        fields = list(summaries[-1])
        writer = csv.DictWriter(f, fields, lineterminator='\n')
        writer.writeheader()
        for s in summaries:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) and k not in ('age_ma', 'history_age_ma')
                                 else ('' if v is None else (f'{v:g}' if isinstance(v, float) else v)))
                             for k, v in s.items()})


if __name__ == '__main__':
    main()
