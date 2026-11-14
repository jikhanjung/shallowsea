"""Scotese 지도와 독립적인 해수면(van der Meer et al. 2022)으로 잠긴 대륙지각을 다시 센다 (devlog 009).

해수면: van der Meer et al. (2022) 부록 1의 1 Myr 간격 곡선(현재 기준, m).
- tect: 스트론튬 동위원소에서 구한 판구조 해수면. 풍화 보정에 같은 고지리 복원을 쓴 기후 모델(SCION)이 들어간다.
- tge: tect + 빙하 해수면. 빙하 부분은 Scotese 기온과 PaleoDEM 면적을 쓴다.
각각 평균(AVG)·최소(MIN)·최대(MAX).

모델 A: PaleoDEM(Scotese) + 회전한 CRUST1.0. 물가를 독립 해수면으로 바꾼다(값 < 해수면).
모델 B: 현대 고도 분포(CRUST1.0에서 물·얼음 하중을 Airy로 뺀 것, airy_sensitivity.py의 modern_relief)를
        고정하고 해수면만 바꾼다. Scotese 자료를 쓰지 않는다. 대륙지각의 모양(부피·두께 분포)이 그대로라는 가정이다.
출력: results/independent_sea_level.csv
"""
import csv
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from crust_points import INPUTS, OCEAN_OR_AMBIGUOUS, ROOT, Plates, atlas_levels, dem_files, load_points, read_dem, sample

K = 1 - 1.03 / 3.30   # 맨틀 3.30, 바닷물 1.03 g/cm³ (airy_sensitivity.py와 같다)
SHEET_NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
COLUMNS = {'tect': ('H', 'I', 'J'), 'tge': ('AI', 'AJ', 'AK')}


def read_curves():
    """부록 1(xlsx)을 표준 라이브러리로 읽는다. {나이(정수 Ma): {'tect': (평균, 최소, 최대), 'tge': (...)}}"""
    with zipfile.ZipFile(INPUTS / 'literature/vandermeer2022_mmc1.xlsx') as z:
        sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    out = {}
    for row in sheet.iter('{%s}row' % SHEET_NS['m']):
        cells = {}
        for c in row.findall('m:c', SHEET_NS):
            v = c.find('m:v', SHEET_NS)
            if v is not None and c.get('t') != 's':
                cells[re.match(r'[A-Z]+', c.get('r')).group()] = float(v.text)
        if 'A' in cells and all(k in cells for cols in COLUMNS.values() for k in cols):
            out[int(round(cells['A']))] = {name: tuple(cells[k] for k in cols) for name, cols in COLUMNS.items()}
    assert len(out) == 541, len(out)
    return out


def modern_relief():
    """CRUST1.0 대륙지각 셀(1°)의 면적(백만 km²)과 물·얼음 하중을 뺀 고도(m). airy_sensitivity.py와 같은 계산."""
    with zipfile.ZipFile(INPUTS / 'crust-thick.zip') as f:
        lon, lat, thickness = np.loadtxt(f.open('crsthk.xyz')).T
    with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as f:
        kind = np.loadtxt(f.extractfile('CNtype1-1.txt'), dtype=str).ravel()
    with tarfile.open(INPUTS / 'crust1.0.tar.gz') as f:
        bounds = np.loadtxt(f.extractfile('crust1.bnds'))
        density = np.loadtxt(f.extractfile('crust1.rho'))
    keep = ~np.isin(kind, OCEAN_OR_AMBIGUOUS)
    lat, bounds, density = lat[keep], bounds[keep], density[keep]
    area = 6371.0088**2 * np.deg2rad(1) * (np.sin(np.deg2rad(lat + .5)) - np.sin(np.deg2rad(lat - .5))) / 1e6
    layers = -np.diff(bounds, axis=1)
    dry = (bounds[:, 2] + (layers[:, :2] * density[:, :2]).sum(axis=1) / 3.30) * 1000
    return area, dry


def main():
    curves = read_curves()
    atlas = atlas_levels()
    lon, lat, kind, thickness, area, volume = load_points()
    plates = Plates(lon, lat)
    relief_area, relief = modern_relief()
    rows = []
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        sl = curves[int(round(age))]
        plat, plon = plates.paleo(age)
        z = sample(read_dem('dem.zip', name, (181, 361)), plat, plon, 1.0)
        valid = np.isfinite(z)
        row = {'age_ma': f'{age:g}', 'map': map_no,
               'atlas_levels': ' '.join(str(a['level']) for a in atlas.get(map_no, []))}
        for curve in ('tect', 'tge'):
            for label, level in zip(('avg', 'min', 'max'), sl[curve]):
                row[f'{curve}_{label}_m'] = level
        for curve in ('tect', 'tge'):
            for label, level in zip(('avg', 'min', 'max'), sl[curve]):
                row[f'A_{curve}_{label}'] = area[valid & (z < level)].sum() / 1e6
                row[f'B_{curve}_{label}'] = relief_area[relief < level].sum()
                # 물가 아래 0–200 m 띠. 모델 B는 바닷물 하중을 Airy로 넣은 수심((해수면 − 고도)/k).
                row[f'A_band_{curve}_{label}'] = area[valid & (z < level) & (z >= level - 200)].sum() / 1e6
                depth = (level - relief) / K
                row[f'B_band_{curve}_{label}'] = relief_area[(depth > 0) & (depth <= 200)].sum()
        rows.append(row)
    with open(ROOT / 'results/independent_sea_level.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
