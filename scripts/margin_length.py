"""되돌린 대륙지각의 연변 길이와, 대륙붕 폭이 일정할 때의 대륙붕 면적 (devlog 010).

- 시점마다 회전한 CRUST1.0 표본점의 면적을 3° 고격자 칸에 모아, 칸 면적의 25% 이상이 차면 대륙으로 본다.
  대륙과 바다의 경계 길이를 잰다(경선 방향 변은 3° 위도 길이, 위선 방향 변은 그 위도의 3° 경도 길이).
  1°나 2° 칸에서는 점을 회전한 뒤 칸에 담는 과정에서 경계가 들쭉날쭉해져, 현재 대륙을 통째로 돌리기만 해도
  길이가 10–80% 늘었다. 3°·25%에서는 이 오차가 +3.8% ± 2.6%다(아래 기준값).
- "그때 없던 지괴를 뺀" 길이: 해수면 0에서 1,400 m보다 깊고 얕은 곳에서 3°보다 먼 표본점(devlog 005)을 뺀다.
- 기준값: 현재 위치의 점을 같은 회전으로 통째로 돌린 다섯 경우의 평균. 실제 겹침·틈이 없는 경우의 길이다.
- 대륙붕 면적 = 연변 길이 × 폭. 폭 = 현재 대륙붕 면적 ÷ 기준값. 현재 대륙붕 면적은 Harris et al. (2014)
  32.24백만 km²와 CRUST1.0 대륙붕 유형(C-) 면적 두 가지로 둔다.
출력: results/margin_length.csv
"""
import csv

import numpy as np
import pygplates as pg

import alignment as al
from crust_points import RADIUS, ROOT, dem_files, read_dem, sample

RES = 3.0
THRESHOLD = 0.25
KM_PER_DEG = RADIUS * np.pi / 180
HARRIS_SHELF = 32.24   # 백만 km², Harris et al. (2014) Table 5
RIGID = (((30, 40), 7.3), ((-20, 100), 23.1), ((60, -50), 41.7), ((10, 10), 90.0), ((-45, 170), 60.0))
NY, NX = int(180 / RES), int(360 / RES)
LAT = 90 - (np.arange(NY) + .5) * RES
CAPACITY = (RADIUS**2 * np.deg2rad(RES) * (np.sin(np.deg2rad(LAT + RES / 2)) - np.sin(np.deg2rad(LAT - RES / 2))))[:, None]


def continent(plat, plon, use):
    iy = np.clip(((90 - plat[use]) / RES).astype(int), 0, NY - 1)
    ix = ((plon[use] + 180) / RES).astype(int) % NX
    total = np.bincount(iy * NX + ix, weights=al.area[use], minlength=NY * NX).reshape(NY, NX)
    return total / CAPACITY >= THRESHOLD


def perimeter(mask):
    """경계 길이(km)."""
    east = (mask != np.roll(mask, -1, axis=1)).sum(axis=1) * KM_PER_DEG * RES
    south = (mask[:-1] != mask[1:]).sum(axis=1) * KM_PER_DEG * RES * np.cos(np.deg2rad(LAT[:-1] - RES / 2))
    return float(east.sum() + south.sum())


def main():
    every = np.ones(len(al.lat), bool)
    points = pg.MultiPointOnSphere([pg.PointOnSphere(float(y), float(x)) for y, x in zip(al.lat, al.lon)])
    rigid = []
    for axis, angle in RIGID:
        c = (pg.FiniteRotation(pg.PointOnSphere(*axis), np.deg2rad(angle)) * points).to_lat_lon_array()
        rigid.append(perimeter(continent(c[:, 0], c[:, 1], every)))
    baseline, spread = float(np.mean(rigid)), float(np.std(rigid))
    shelf_c = al.area[al.kind == 'C-'].sum() / 1e6
    width_h, width_c = HARRIS_SHELF * 1e6 / baseline, shelf_c * 1e6 / baseline
    rows = []
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        l_all = perimeter(continent(plat, plon, valid))
        l_kept = perimeter(continent(plat, plon, valid & ~far))
        rows.append({'age_ma': f'{age:g}', 'map': map_no, 'margin_km': l_all, 'margin_without_far_terranes_km': l_kept,
                     'margin_ratio': l_all / baseline, 'margin_without_far_ratio': l_kept / baseline,
                     'shelf_harris_width': l_all * width_h / 1e6, 'shelf_harris_width_without_far': l_kept * width_h / 1e6,
                     'shelf_crust1_width': l_all * width_c / 1e6, 'far_terrane_area': al.area[far].sum() / 1e6})
    with open(ROOT / 'results/margin_length.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})
    identity = perimeter(continent(al.lat, al.lon, every))
    print(f'identity {identity:.0f} km, rigid baseline {baseline:.0f} ± {spread:.0f} km ({spread / baseline:.3f}); '
          f'width Harris {width_h:.1f} km, CRUST1 C- {shelf_c:.2f} → {width_c:.1f} km')


if __name__ == '__main__':
    main()
