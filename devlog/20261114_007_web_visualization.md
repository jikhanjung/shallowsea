# 007 — 단계별 결과를 보여 주는 웹 페이지와 dolfinid 배포

날짜: 2026-11-14

## 요청

사용자: "docker image 하나 만들어서 dolfinid 에 shallowsea.nopeoplestime.info 로 올려줘. 단계별로 알아낸 것이 뭔지, 그 결과를 시각화해서 보여줘. 세계지도로 보여줘야 할 때는 몰바이데 투영으로 … ETT repo 살펴보고 회전 가능한 몰바이데 투영으로 만들어서."

## 만든 것

- `web/`: 정적 페이지(HTML·CSS·ES 모듈, 외부 라이브러리 없음).
  - `mollweide.js`: 회전 가능한 몰바이데 지도. EarthThruTime3D(`static/core/projection.js`, `docs/globe-viewer.md`)의 방식을 따랐다. 평면이 극축을 중심으로 돌아 중앙 경선이 바뀌고(좌우 끌기, 화살표 키, 자동 회전), 픽셀마다 역투영해 경위도의 값을 읽는다. 경위선과 벡터 도형(Macrostrat 단면)은 같은 이동을 거쳐 그리고 이음매에서 끊는다. ETT처럼 확대와 세로 이동(+ − 단추, 키)도 넣었다.
  - `charts.js`: SVG 시계열·점·막대 차트. 십자선과 툴팁이 있고, 누르면 그 시점으로 간다. 오른쪽 끝 계열 이름은 서로 밀어내 겹치지 않게 한다.
  - `app.js`: 위쪽 시점 막대 하나에 모든 지도와 차트가 따라간다.
  - 구성: 첫머리 요약 → 001 출발점 → 003 PaleoDEM의 값(지도·값별 면적·단일값과 아틀라스 해수면·해수면 0 면적) → 004 물가 아래 잠긴 대륙지각(지도·시계열) → 005 정렬 검사(지도·유형별 깊은 지각·판 겹침·판 표) → 006 Macrostrat(북미 확대 지도·시계열) → 한계.
- 색은 dataviz 지침의 기본 팔레트를 썼다. 지도 범주는 모든 쌍을 구별해야 해서 세 색(파랑·주황·청록)과 회색만 쓴다. 네 색(빨강 추가)은 검증기에서 주황과 구별되지 않아 떨어졌다. 그래서 Macrostrat 지도는 "모델과의 일치"와 "기록 종류" 두 보기로 나눴고, 판 겹침은 색 대신 점무늬로 표시한다. 밝은·어두운 모드를 따로 정했다.
- `scripts/build_site_data.py`(약 1분): `results/`와 원자료에서 `web/data/`를 만든다(git에 올리지 않는다).
  - `dem/<나이>.bin`: 0.1° 격자에서 0.5°마다 뽑은 int16(한 장 520 KB, gzip 약 55 KB).
  - `crust_sea_level_0.bin`, `crust_atlas.bin`: 시점 × 1° 고격자의 대륙지각 상태(없음·물가 위·잠김·깊음·깊고 멂, + 판 겹침). 칸마다 표본점 면적이 가장 큰 상태다(각 7.1 MB, gzip 약 570 KB).
  - `macrostrat.json`: 단면 다각형(좌표 0.01° 반올림)과 시점별 상태, `summary.json`, `hist.json`.
- `deploy/`: `Dockerfile`(nginx 1.27.3-alpine, 정적 파일을 미리 gzip해 `gzip_static`으로 보냄, `/healthz`), `nginx.conf`, `VERSION`, `deploy.sh`, `host/`(compose, Nginx 사이트 설정).

## 확인

- 로컬 http 서버와 컨테이너 양쪽에서 Playwright(hanyang3d의 가상환경을 빌림)로 1200 px 밝은·어두운 모드와 390 px 휴대폰 폭을 렌더링했다. 콘솔 오류가 없고 가로 넘침도 없다.
- 컨테이너는 읽기 전용 루트, tmpfs, `cap_drop: ALL`(CHOWN·SETUID·SETGID·NET_BIND_SERVICE만 다시 줌), `no-new-privileges`로 떴다.
- 처음 만든 nginx 설정에 `types { application/octet-stream bin; }`를 넣었더니 기본 MIME 표 전체를 덮어써 `index.html`이 내려받기로 나갔다. 그 줄을 지웠다(`.bin`은 기본 표에 이미 있다).

## 배포

(배포 뒤 덧붙인다.)

## 한계

- DEM은 0.5° 점 표본이라 확대하면 계단이 보인다.
- Macrostrat 지도는 현대 위치에 그린다. 단면을 시점마다 고위치로 옮기지는 않았다.
- 판 이름은 자료에 없어, 표의 지역은 현대 위치와 지각 유형으로 짐작했다(devlog 005).
