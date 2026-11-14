# HANDOFF — 2026-11-13 현재 상태 · shallowsea

이어서 작업할 사람(또는 다음 세션)이 읽는 인계 문서다. **지금** 무엇이 되어 있고, 어디에 함정이 있는지만 적는다. 지난 계산의 방법과 수치는 `devlog/`([001](devlog/20261113_001_paleodem_crust1_baseline.md))에, 할 일은 [TODOs.md](TODOs.md)에, 문헌은 [docs/references.md](docs/references.md)에 있다.

**저장소**: `git@github.com:jikhanjung/shallowsea.git`, 브랜치 `main`.

**웹 페이지**: https://shallowsea.nopeoplestime.info = `v0.6.0`(커밋 `2acd138`, 2026-11-14, digest `sha256:fe41af9c…`). 상단 단계별 메뉴로 한 단계씩 본다. 처음 배포와 구성은 [devlog 007](devlog/20261114_007_web_visualization.md). dolfinid `/srv/shallowsea`, 컨테이너 `shallowsea-shallowsea-1`, `127.0.0.1:8019`, Nginx 사이트 `shallowsea`, 인증서 만료 2027-02-12(자동 갱신). 결과를 바꾸면 `scripts/build_site_data.py` → 이미지 빌드·push → `bash deploy/deploy.sh <판>`.

## 배경과 가설

출발점은 “캄브리아기에 얕은 바다가 유난히 많았다”는 서술이다. 로렌시아의 소크 해침과 대륙 내부의 해성 퇴적층은 강한 지역 증거다. 그러나 다음 세 가지는 서로 다른 관측량이다.

- 지층의 연대와 퇴적상으로 제약할 수 있는 해침 범위
- 여러 시점을 합친 해성층 분포
- 한 시점의 전 지구 절대 수심 분포

특히 대륙내해는 허드슨만처럼 대륙 안쪽을 침수하며, 현대 해저지형에서 측정한 대륙붕단까지의 면적과도 정의가 다르다. Harris et al. (2014)의 현대 대륙붕 면적은 3,224만 km²다.

사용자의 가설은 현생누대에 대륙지각의 면적과 평균 두께 및 부피가 준평형에 가까웠을 수 있다는 것이다. 사용자의 말과 그 검증은 [docs/rationale.md](docs/rationale.md)에 있다: 부피 일정은 문헌상 합리적이고, "물가 아래 0–200 m 띠 면적이 크게 변하지 않는다"는 약한 형태도 현대 대륙 모양에서는 버틴다(17–28백만 km²). "잠긴 대륙 면적이 일정하다"는 강한 형태는 해수면 변화 때문에 성립하지 않는다. 지각의 생성·소실과 판 변형에 따른 변화는 허용한다. 이 가설은 대륙 범위를 임의의 수심 경계로 정의해 얻은 면적의 물리적 타당성을 검사하는 데 쓸 수 있다. 면적과 부피를 맞춰도 얕은 수심대에 들어가는 면적은 해수면 부근의 고도–면적 분포, 분지 침강과 상대 해수면에 달려 있다.

## 지금 되어 있는 것

| 계산 | 스크립트 | 결과 |
|---|---|---|
| CRUST1.0 대륙지각을 PALEOMAP v3로 109개 시점(0–540 Ma)에 역회전해 물가(해수면 0, 아틀라스 해수면) 아래로 잠긴 면적·부피 집계. 옛 수심대별 집계도 같이 쓴다 | `scripts/reconstruct.py` | `results/PALEOMAP_CRUST1_waterline_0-540Ma.csv`, `results/PALEOMAP_CRUST1_0-540Ma.csv` |
| 고도 분포 두 개(현대 지형, Airy)에 균일한 상대 해수면 변화를 주는 민감도 실험. 육지 면적 목표는 물가 기준 CSV에서 읽는다 | `scripts/airy_sensitivity.py` | `results/airy_sensitivity.txt` |
| PaleoDEM 150–200 m 구간의 수심값 빈도와 위도별 면적 | `scripts/depth_audit.py` | `results/depth_audit.txt` |
| PaleoDEM 1°·0.1° 109장의 값별 면적과 지도별 단일값 | `scripts/depth_classes.py` | `results/depth_classes.csv`, `results/depth_classes_summary.csv` |
| 회전한 지각과 DEM의 정렬: 깊은 지각, 판 겹침, 중복 제거 면적, 회전 나이 시험 | `scripts/alignment.py` (공용 모듈 `crust_points.py`) | `results/alignment_summary.csv`, `alignment_plates.csv`, `alignment_age_shift.csv` |
| Macrostrat 해성층 단면 면적과 같은 범위의 모델 잠김 비교(북미 1, 남미 8). 현대 모양에서 해성 단면을 잠기게 하는 데 필요한 해수면 | `scripts/macrostrat_compare.py [프로젝트]` | `results/macrostrat_north_america.csv`, `macrostrat_columns_agreement.csv`, `macrostrat_south_america*.csv` |
| 아틀라스 그림과 DEM을 겹쳐 해수면 표와 지도 번호 대응을 확인. 다른 스크립트의 아틀라스 해수면은 이 대응을 따른다 | `scripts/atlas_check.py` | `results/atlas_sea_level_check.csv` |
| Scotese와 독립적인 해수면(van der Meer et al. 2022)으로 잠긴 대륙지각: Scotese 지형(모델 A)과 현대 대륙 모양 고정(모델 B) | `scripts/independent_sea_level.py` | `results/independent_sea_level.csv` |
| 회전한 대륙지각의 연변 길이(3° 칸, 강체 회전 기준값 대비)와 대륙붕 폭을 고정했을 때의 대륙붕 면적 | `scripts/margin_length.py` | `results/margin_length.csv` |
| Scotese 지형의 고도를 현대 고도–두께 관계로 두께로 바꿔 대륙지각 부피를 시점별로 계산 | `scripts/crust_volume.py` | `results/crust_volume.csv`, `crust_volume_calibration.csv` |
| 단계별 결과 웹 페이지 자료 | `scripts/build_site_data.py` | `web/data/`(git 제외), 페이지는 `web/`, 이미지는 `deploy/` |

PaleoCoastlines `areas.csv`로 한 면적·부피 수지와 원본 PaleoDEM 전 지구 수심 면적은 스크립트 없이 devlog 001에 수치만 남아 있다.

**m710q에서 재현된다**(2026-11-14, [devlog 002](devlog/20261114_002_reproduce_on_m710q.md)). Python 3.13.17, NumPy 2.5.4, pyGPlates 1.0.0, GDAL 3.12.2로 세 스크립트를 다시 돌렸다. CSV와 `depth_audit.txt`는 바이트 단위로 같고, `airy_sensitivity.txt`는 첫 줄의 두 합계만 마지막 자리(약 1e-16)가 다르다. 절차는 [README.md](README.md)에 있다.

## 지금 쓰는 정의

**얕은 바다를 수심으로 나누지 않고, 물가 아래로 잠긴 CRUST1.0 대륙지각의 면적·부피를 센다**([devlog 004](devlog/20261114_004_waterline_definition.md), 2026-11-14 사용자와 정함). 물가는 PaleoAtlas 지도에 적힌 해수면이 기본이고(판이 여럿이면 범위), 해수면 0은 민감도다. 보간 지도 23개는 아틀라스 해수면이 없어 해수면 0 결과만 있다.

아틀라스 해수면 표와 지도 번호 대응은 그림을 DEM과 겹쳐 확인했다([devlog 008](devlog/20261114_008_atlas_sea_level_check.md)). 108장 모두 92.7–98.6% 일치하고, 번호가 어긋난 5장(Map 60, 61, 79, 85)은 그림이 맞는 DEM에 대응시켰다. 해수면과 같은 값의 칸을 바다로 칠했는지는 지도마다 달라 아틀라스 기준 면적은 "칸 제외/포함" 범위로 본다.

이 정의에서 캄브리아기(500 Ma 99.1–101.0, 520 Ma 104.9–108.8백만 km²)는 가장 많지 않다. 데본기·실루리아기·오르도비스기(380 Ma 114.8–118.4, 425 Ma 114.0–117.3, 480 Ma 111.7–117.0)가 더 크다. 다만 아틀라스 해수면은 지도마다 다른 계통역(최대 범람면, 초층서 경계 등)을 그린 Scotese의 해석이라, 시점끼리 비교하면 고해수면 지도와 저해수면 지도가 섞인다.

**북미에서는 Macrostrat 해성층 기록도 같은 방향이다**([devlog 006](devlog/20261114_006_macrostrat_north_america.md)). 해성층 단면 면적은 450 Ma(9.9백만 km²)에 정점이 있고 500 Ma는 6.4, 520 Ma는 2.8이다. 모델과의 순위 상관은 고생대 0.81이다. 다만 Scotese가 해수면을 침수 증거에 맞췄고 같은 문헌을 썼을 수 있어 독립 검증이 아니라 일관성 검사다. 모델은 고생대 북미의 60–90%를 잠기게 하는데, 해성층 단면은 그 절반 이하이고 비해성층만 있는 단면도 상당수 잠긴다.

**Scotese와 독립적인 해수면을 쓰면 캄브리아기 침수를 지지하는 계산이 없다**([devlog 009](devlog/20261114_009_independent_sea_level.md)). 스트론튬 기반 판구조 해수면은 500 Ma를 −18 m(−65 ~ +17), 450 Ma를 +88 m로 둔다. 현대 대륙 모양을 고정하면 500 Ma의 잠긴 대륙지각은 109개 시점 중 108번째로 작다. Scotese 지형에서 0–200 m 띠는 현대 모양의 상한(28.2백만 km²)을 52개 시점에서 넘는다.

**등압평형만 가정하면 부피 일정 가설과 Scotese 고생대 지도는 함께 성립하지 않는다**([devlog 011](devlog/20261114_011_crust_volume.md)). 그러나 해성층 기록은 고생대 대륙 안쪽이 현대 모양보다 해수면에 대해 수백 m 낮았다고 말한다(북미 중앙값 +435 m, 남미 +243 m, [devlog 012](devlog/20261114_012_south_america_and_modern_shape.md)). 그 원인이 동적 지형·열침강이면 고도 효과는 부피와 무관하고 면적 부족(약 18%p)만 남는다. "부피 일정"은 버틸 수 있지만 "모양 일정"은 기록과 맞지 않는다. 캄브리아기 대륙(그때 없던 지괴·겹침 제외)은 면적 0.82배, 평균 두께 0.92배로 부피가 현재의 약 0.75배다. 연변 길이로 본 대륙붕 면적은 ±20% 안에서 움직이고 캄브리아기가 두드러지지 않는다([devlog 010](devlog/20261114_010_margin_length.md)).

판 겹침을 빼는 **지도상 중복 제거 면적**도 있다([devlog 005](devlog/20261114_005_alignment_check.md), `alignment_summary.csv`의 `dedup_*`). 아틀라스 해수면 최대 판 기준 500 Ma 90.4, 380 Ma 107.1백만 km²로, 순위는 같다.

## 함정

- **PaleoDEM의 해수면 부근 값은 측정된 수심이 아니다**([devlog 003](devlog/20261114_003_paleodem_depth_classes.md)). 모든 값이 40 m 간격(256단계 그레이스케일)이다. 80–160 Ma와 250–540 Ma 지도는 대륙내해로 보이는 넓은 지역을 한 값으로 칠했고, 그 값이 지도마다 다르다: 대부분 −160 m, 250 Ma −40 m, 255 Ma −80 m, 230·235·245 Ma 0 m, 180·200·240 Ma +40 m. 500 Ma 0–200 m 58.7백만 km² 가운데 46.4가 −160 m 단일값이다. 그래서 해수면 0에서 150 m, 200 m 경계로 자른 비교(devlog 001의 "현대의 약 3배, 150 m 기준 역전", "88%가 150–200 m", Airy 실험의 150–200 m 표)는 칠한 값의 선택을 비교한 것이다.
- **260 → 240 Ma의 급감(41.7 → 2.7)은 240 Ma 단일값이 +40 m라 육지로 세어진 결과다.** 230·235·245 Ma는 단일값이 정확히 0 m라 "0 < 수심" 기준에서 빠진다.
- **Scotese의 PaleoAtlas 지도는 지도마다 다른 해수면(−120 ~ +160 m)으로 그려졌다**(`docs/paleoatlas_sea_levels.csv`). 해수면 0으로 센 면적은 Scotese가 그린 해안선과 다를 수 있다(245 Ma: 6.1 대 35.8).
- **1°는 0.1°의 점 표본이다.** 1° 결과와 0.1° 결과의 차이는 표본 오차이고 독립 증거가 아니다. EarthByte와 Zenodo의 1° zip은 같은 파일이다.
- **면적의 기준을 섞지 않는다.** PaleoDEM 원본 면적, Kocsis–Scotese −1,400 m 경계 집계, CRUST1.0 지각 추적 면적(판이 겹치면 중복 합산), 지도상 중복 제거 면적은 서로 다른 값이다.
- **역회전은 복원이 아니다.** 현대 지각의 면적·두께를 그대로 옮긴 것이고 과거 지각 두께가 아니다. 그 결과가 두 가지로 드러난다(devlog 005).
  - **그때 없던 지각까지 센다.** 500 Ma에 해수면 0에서 1,400 m보다 깊은 곳에 놓인 대륙지각 31.3백만 km² 가운데 19.8이 얕은 곳에서 3° 넘게 떨어진 대양에 있다. 대부분 서시베리아·카자흐스탄, 몽골–아무르, 투란, 오호츠크, 북미 코딜레라, 서남극처럼 나중에 붙은 지괴다.
  - **판이 겹친다.** 늘어난 대륙연변을 강체로 되돌려 150 Ma 이후 약 15백만 km²가 두 번 세어진다(남미–아프리카, 호주–남극 등). 추적 면적은 지도상 면적이 아니다.
- **회전 파일은 PaleoDEM과 같은 판 모델이다.** 회전 나이를 ±5, ±10 Myr 비틀면 맞음 지표가 대부분 원래 나이에서 가장 좋다(devlog 005).
- **순환 검증을 피한다.** Kocsis–Scotese 해안선은 해양화석 위치로 보정됐다. 시점별 Scotese 육지 면적에 맞춘 해수면은 독립적인 고해수면 추정이 아니다.

## 다음

순서는 [devlog P01](devlog/20261114_P01_validation_plan.md)의 계획을 따른다. 1단계(정의, devlog 004), 2단계(정렬 검사, devlog 005), 3단계의 북미 부분(Macrostrat, devlog 006)을 했다. 1단계의 아틀라스 그림 겹치기, 2단계의 지도 그리기, 3단계의 다른 대륙과 퇴적상 수심이 남았다. 그 다음은 독립 해수면과 지역 침강 → 면적·부피와 변형. 항목별 할 일은 [TODOs.md](TODOs.md)에 있다.
