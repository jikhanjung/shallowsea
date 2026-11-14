"""PaleoAtlas 지도 그림의 바다색과 PaleoDEM을 겹쳐, 그림을 가장 잘 재현하는 해수면을 찾는다 (devlog 008).

그림 왼쪽 아래에 적힌 해수면(docs/paleoatlas_sea_levels.csv, 눈으로 옮겨 적음)과 이 값이 같으면
옮겨 적은 표와 "아틀라스 지도 번호 = PaleoDEM 지도 번호"라는 대응이 함께 확인된다.

- 그림: inputs/paleoatlases.zip의 PDF 페이지를 pdftoppm으로 1800 × 900 픽셀로 그린다. 몰바이데 타원이 화면을
  꽉 채운다고 보고, 중앙 경선 0°로 역투영한다.
- 바다: 파랑 성분이 빨강보다 15 넘게 크고 초록 이상인 픽셀. 글자가 있는 네 모서리는 뺀다.
- DEM: 같은 번호의 0.1° 격자에서 최근접 값.
출력: results/atlas_sea_level_check.csv
"""
import csv
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from crust_points import ROOT, INPUTS, dem_files, read_dem

W, H = 1800, 900
CANDIDATES = list(range(-200, 201, 40))
# 이웃 지도의 DEM이 이만큼 넘게 더 잘 맞으면 그 DEM에 대응시킨다(devlog 008).
REASSIGN_MARGIN = 0.015
# PDF마다 지도 페이지: 1쪽 표지, 2쪽 소개 다음부터 CSV의 행 순서대로. 4.3의 11쪽은 지도가 아니다.
PDFS = [('1.1', range(3, 13)), ('1.2', range(3, 15)), ('2.1', range(3, 16)), ('2.2', range(3, 15)),
        ('3.1', range(3, 16)), ('3.2', range(3, 13)), ('4.1', range(3, 18)), ('4.3', range(3, 11)),
        ('5.1', range(3, 12)), ('5.2', range(3, 11))]


def render(pdf, page, tmp):
    out = Path(tmp) / 'page'
    subprocess.check_call(['pdftoppm', '-f', str(page), '-l', str(page), '-scale-to-x', str(W), '-scale-to-y', str(H),
                           str(pdf), str(out)], stderr=subprocess.DEVNULL)
    path = next(Path(tmp).glob('page*.ppm'))
    data = path.read_bytes()
    path.unlink()
    parts = data.split(maxsplit=4)
    w, h = int(parts[1]), int(parts[2])
    assert (w, h) == (W, H), (pdf, page, w, h)
    return np.frombuffer(parts[4][-w * h * 3:], np.uint8).reshape(h, w, 3).astype(int)


def pixel_lonlat():
    """화면 픽셀의 경위도(타원 밖은 NaN)와 쓸 픽셀 마스크."""
    x = (np.arange(W) + 0.5) / W * 2 - 1
    y = 1 - (np.arange(H) + 0.5) / H * 2
    x, y = np.meshgrid(x, y)
    inside = x ** 2 + y ** 2 < 0.97 ** 2   # 테두리선을 뺀다
    theta = np.arcsin(np.clip(y, -1, 1))
    lon = x / np.maximum(np.cos(theta), 1e-9) * 180
    lat = np.degrees(np.arcsin((2 * theta + np.sin(2 * theta)) / np.pi))
    corners = np.zeros((H, W), bool)
    corners[:H // 6, :W // 4] = corners[:H // 6, -W // 4:] = True
    corners[-H // 6:, :W // 3] = corners[-H // 6:, -W // 4:] = True
    use = inside & ~corners & (np.abs(lon) <= 180)
    return lon, lat, use


def main():
    rows = list(csv.DictReader(open(ROOT / 'docs/paleoatlas_sea_levels.csv')))
    # 지도 번호는 1° 배포본(보고서 Table 1과 같다)에서 나이로 바꾸고, 0.1° 격자는 나이로 찾는다.
    # 0.1° 배포본은 280·285 Ma의 번호가 엇갈린다(devlog 003).
    by_age = {round(a): n for m, a, n in dem_files('dem_6min.zip')}
    files = {m: (a, by_age[round(a)]) for m, a, n in dem_files('dem.zip')}
    chain = sorted(files, key=lambda m: files[m][0])
    cache = {}

    def grid_values(map_no):
        if map_no not in cache:
            cache[map_no] = read_dem('dem_6min.zip', files[map_no][1], (1801, 3601))[iy, ix]
        return cache[map_no]
    lon, lat, use = pixel_lonlat()
    iy = np.clip(np.round((90 - lat[use]) * 10).astype(int), 0, 1800)
    ix = np.clip(np.round((lon[use] + 180) * 10).astype(int), 0, 3600)
    out = []
    order = iter(rows)
    with zipfile.ZipFile(INPUTS / 'paleoatlases.zip') as archive, tempfile.TemporaryDirectory() as tmp:
        names = {Path(n).name[:3]: n for n in archive.namelist() if n.endswith('.pdf')}
        for key, pages in PDFS:
            pdf = Path(tmp) / f'{key}.pdf'
            pdf.write_bytes(archive.read(names[key]))
            for page in pages:
                row = next(order)
                image = render(pdf, page, tmp)[use]
                r, g, b = image[:, 0], image[:, 1], image[:, 2]
                sea = (b - r > 15) & (b >= g)
                map_no = row['atlas_map']
                if map_no not in files:
                    continue
                age, name = files[map_no]
                z = grid_values(map_no)
                score = {s: float(((z < s) == sea).mean()) for s in CANDIDATES}
                # 대응 시험: 앞뒤 두 지도씩의 DEM과도 겹쳐, 해수면을 각자 가장 잘 맞게 골랐을 때 누가 가장 잘 맞는가.
                k = chain.index(map_no)
                neighbours = {}
                for other in chain[max(0, k - 2):k + 3]:
                    zo = grid_values(other)
                    neighbours[other] = max(float(((zo < s) == sea).mean()) for s in CANDIDATES)
                rival = max((m for m in neighbours if m != map_no), key=neighbours.get)
                best = max(score, key=score.get)
                caption = int(row['sea_level_m'])
                out.append({'pdf': key, 'page': page, 'atlas_map': map_no, 'dem_age_ma': f'{age:g}',
                            'caption_sea_level_m': caption, 'best_sea_level_m': best,
                            'agreement_caption': score.get(caption), 'agreement_best': score[best],
                            'agreement_sea_level_0': score[0], 'atlas_sea_share': float(sea.mean()),
                            'best_rival_map': rival, 'agreement_best_rival': neighbours[rival],
                            'matched_dem_map': rival if neighbours[rival] - score[best] > REASSIGN_MARGIN else map_no,
                            'systems_tract': row['systems_tract'],
                            **{f'agree_{s}': score[s] for s in CANDIDATES}})
                print(key, page, map_no, caption, best, round(score[best], 4), flush=True)
    assert next(order, None) is None
    with open(ROOT / 'results/atlas_sea_level_check.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, list(out[0]), lineterminator='\n')
        writer.writeheader()
        for r in out:
            writer.writerow({k: (f'{v:.5f}' if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
