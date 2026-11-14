"""그때 없던 지괴(devlog 005)를 지질 구역별로 묶어 면적과 현재 부피를 낸다 (devlog 018).

질문: 500 Ma 지도에서 빠지는 대륙지각 면적 몫(약 10%p, devlog 016) 가운데 문헌상 500 Ma 이후 새로 만들어진
지각은 얼마인가? 이 스크립트는 문헌 비율을 곱할 바탕(구역별 면적과 현재 부피)만 낸다. 문헌 비율과 곱셈은 devlog 018.

그때 없던 지괴의 정의는 crust_volume.py와 같다(물가 아래 1,400 m보다 깊고 얕은 곳에서 3°보다 멂).
현재 부피 = 표본점 면적 × 0 Ma 지도의 고도로 낸 두께(crust_volume.py의 보간), 즉 그 지각이 지금 가진 부피.
구역은 판 번호를 손으로 묶었다(500 Ma에서 그때 없던 지괴 면적이 큰 판 위주, 현대 위치로 판단). 나머지는 '기타'.
출력: results/far_terrane_groups.csv (면적 백만 km², 부피 십억 km³)
"""
import csv

import numpy as np

import alignment as al
from crust_points import ROOT, dem_files, read_dem, sample
from crust_volume import calibration
from independent_sea_level import K

REGIONS = {
    'caob': ('중앙아시아 조산대(서시베리아·카자흐스탄, 몽골–아무르, 투란)', [402, 628, 514, 513, 407, 511]),
    'cordillera': ('북미 코딜레라·알래스카', [121, 123, 125, 126, 127, 128, 129, 130, 140]),
    'ne_russia': ('북동 러시아(콜리마–오몰론, 추코트카 등)', [403, 405, 406, 408, 410, 420]),
    'barents_arctic': ('바렌츠·카라 해 등 북극', [301, 309, 310, 409, 102]),
    'west_antarctica': ('서남극', [803, 804]),
    'zealandia': ('질랜디아·호주 동쪽 해저고원', [806, 813, 814, 824, 826, 833, 840, 846]),
    'se_asia': ('동남아·뉴기니', [615, 619, 620, 626, 664, 671, 676, 679, 800]),
    'caribbean': ('카리브·중미', [135, 204, 206, 222, 223, 224, 230, 239, 252, 902]),
}


def main():
    centres, means, _ = calibration()
    thick = lambda d: np.interp(d, centres, means)
    region = np.full(al.plates.plate_id.shape, 'other', dtype=object)
    for key, (_, ids) in REGIONS.items():
        region[np.isin(al.plates.plate_id, ids)] = key
    keys = list(REGIONS) + ['other']
    rows, reference = [], None
    for map_no, age, name in sorted(dem_files('dem.zip'), key=lambda r: r[1]):
        plat, plon = al.plates.paleo(age)
        valid = np.isfinite(plat)
        g1 = read_dem('dem.zip', name, (181, 361))
        z = sample(g1, plat, plon, 1.0)
        dry = np.nan_to_num(np.where(z < 0, z * K, z))
        if reference is None:
            reference = al.area * thick(dry)            # 0 Ma 지도: 표본점의 현재 부피(km³)
            total_volume = reference[valid].sum()
            total_area = al.area[valid].sum()
        iy, ix = al.cell_index(np.where(valid, plat, 0), np.where(valid, plon, 0))
        far = valid & (z < -1400) & (al.distance_class(g1[:, :360] >= -200, iy, ix) == 99)
        row = {'age_ma': f'{age:g}', 'map': map_no,
               'far_area': al.area[far].sum() / 1e6, 'far_area_share': al.area[far].sum() / total_area,
               'far_present_volume': reference[far].sum() / 1e9,
               'far_present_volume_share': reference[far].sum() / total_volume}
        for k in keys:
            m = far & (region == k)
            row[f'{k}_area'] = al.area[m].sum() / 1e6
            row[f'{k}_present_volume'] = reference[m].sum() / 1e9
        rows.append(row)
    with open(ROOT / 'results/far_terrane_groups.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
