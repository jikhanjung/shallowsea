# shallowsea

캄브리아기와 판게아 시기의 얕은 바다 면적을 PALEOMAP에서 재계산하고, 지각 면적·부피와 등압평형을 적용했을 때 그 수심 분포가 재현되는지 검증하는 프로젝트.

- [현재 상태와 함정](HANDOFF.md), [할 일](TODOs.md), [진행 기록](devlog/README.md), [문헌](docs/references.md)
- [물가 기준별 잠긴 대륙지각](results/PALEOMAP_CRUST1_waterline_0-540Ma.csv) — 지금 쓰는 정의(devlog 004)
- [109개 시점의 CRUST1.0–PaleoDEM 중첩 결과](results/PALEOMAP_CRUST1_0-540Ma.csv) — 해수면 0에서 수심대로 나눈 옛 집계
- [Airy 등압평형 민감도 실험](results/airy_sensitivity.txt)
- [PaleoDEM 원본의 수심 빈도 검사](results/depth_audit.txt)
- [PaleoDEM 1°·0.1° 값별 면적](results/depth_classes.csv)과 [지도별 요약](results/depth_classes_summary.csv)
- [PaleoAtlas 지도별 해수면 설정](docs/paleoatlas_sea_levels.csv)과 [그림·DEM 대조](results/atlas_sea_level_check.csv)
- [독립 해수면(van der Meer et al. 2022)으로 센 잠긴 대륙지각](results/independent_sea_level.csv)
- [연구의 근거와 검증](docs/rationale.md)
- [대륙 연변 길이와 대륙붕 면적](results/margin_length.csv)
- [Scotese 지형이 담는 대륙지각 부피](results/crust_volume.csv)와 [지역별 부족](results/crust_volume_by_region.csv)
- [회전한 지각과 DEM의 정렬 검사](results/alignment_summary.csv): 깊은 지각, 판 겹침, 중복 제거 면적
- [Macrostrat 북미 해성층과 모델 잠김 비교](results/macrostrat_north_america.csv)와 [단면 단위 일치표](results/macrostrat_columns_agreement.csv), [남미](results/macrostrat_south_america.csv)

## 웹 페이지

단계별 결과를 회전 가능한 몰바이데 지도와 차트로 보여 주는 정적 페이지가 `web/`에 있다(devlog 007). 운영 주소는 https://shallowsea.nopeoplestime.info 이다.

```bash
python scripts/build_site_data.py        # web/data/ 생성 (아래 재현을 먼저 돌린다)
python -m http.server -d web 8765        # 로컬에서 보기
docker build --platform linux/amd64 -f deploy/Dockerfile \
  --build-arg VERSION=$(cat deploy/VERSION) --build-arg COMMIT=$(git rev-parse --short HEAD) \
  -t honestjung/shallowsea:$(cat deploy/VERSION) .
docker push honestjung/shallowsea:$(cat deploy/VERSION)
bash deploy/deploy.sh $(cat deploy/VERSION)   # dolfinid /srv/shallowsea, 127.0.0.1:8019
```

## 재현

Python 3.13(pyGPlates 1.0.0의 wheel은 cp38–cp313까지만 있어 3.14에는 설치되지 않는다), GDAL의 `gdal_translate`(NetCDF 드라이버 포함), curl, unzip이 필요하다. 최초 실행에서 공개 원본 자료를 내려받는다.

```bash
uv venv --python 3.13 .venv   # uv가 없으면 python3.13 -m venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt   # 또는 python -m pip install -r requirements.txt
bash scripts/download.sh
sha256sum -c docs/input-sha256.txt
grep -v '^#' docs/macrostrat-sha256.txt | sha256sum -c   # 2026-11-14에 받은 Macrostrat. 다시 받으면 다를 수 있다
python scripts/atlas_check.py            # 아틀라스 그림과 DEM 대응(devlog 008). 아래 스크립트가 이 결과를 읽는다
python scripts/reconstruct.py
python scripts/airy_sensitivity.py > results/airy_sensitivity.txt
python scripts/depth_audit.py > results/depth_audit.txt
python scripts/depth_classes.py
python scripts/alignment.py
python scripts/macrostrat_compare.py 1   # 북미
python scripts/macrostrat_compare.py 8   # 남미
python scripts/independent_sea_level.py
python scripts/margin_length.py
python scripts/crust_volume.py
python scripts/crust_volume_by_region.py
```

커밋된 결과(3e390d2)는 NumPy 2.3.5, pyGPlates 1.0.0, GDAL 3.10.3에서 만들었다. m710q에서 Python 3.13.17, NumPy 2.5.4, pyGPlates 1.0.0, GDAL 3.12.2로 다시 돌려 같은 결과를 얻었다(2026-11-14, [devlog 002](devlog/20261114_002_reproduce_on_m710q.md)). `airy_sensitivity.txt` 첫 줄의 합계 두 개는 마지막 자리가 다르게 나온다. 원자료와 인용은 [docs/references.md](docs/references.md)를 참조한다.
