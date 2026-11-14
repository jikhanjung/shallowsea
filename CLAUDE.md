# CLAUDE.md

**shallowsea** — 캄브리아기와 판게아 시기의 얕은 바다 면적을 PALEOMAP에서 재계산하고, 지각 면적·부피와 등압평형을 적용했을 때 그 수심 분포가 재현되는지 검증하는 연구 저장소.
문서는 한국어로 쓴다. 커밋 메시지, devlog, 주석 모두 해당한다.

`AGENTS.md`는 이 파일을 가리키는 심볼릭 링크다. 지침은 이 파일에만 쓴다.

## 시작하기 전에 읽을 것

**[HANDOFF.md](HANDOFF.md)부터** 읽는다. 지금 무엇이 되어 있고 어디에 함정이 있는지 적혀 있다. 할 일은 [TODOs.md](TODOs.md)에, **왜 그렇게 계산했는지는 `devlog/`에**, 문헌은 [docs/references.md](docs/references.md)에 있다. 기존 결과의 재현 방법은 [README.md](README.md)에 있다.

## 연구 규칙

- PaleoDEM 원본, Kocsis–Scotese의 −1,400 m 경계 집계, CRUST1.0 지각 추적 면적, 실제 지도상 중복 제거 면적은 각각 계산 기준을 명시한다.
- 원본 현대 지각의 역회전과 과거 실제 지각 두께의 복원을 구별한다. 부피를 보존하도록 설계한 경우 그 값은 독립 검증 결과로 쓰지 않는다.
- 절대 수심 검증은 자료가 허용하는 범위와 연대 불확실성을 기록한다. 화석 및 퇴적상 자료로 모델을 보정했다면 같은 자료와의 일치도를 독립 검증으로 보고하지 않는다.
- 계산을 갱신하면 방법, 입력 버전, 결과, 확인한 한계를 문서에 기록한다. 기록하는 곳은 devlog이고, HANDOFF.md의 현재 상태도 함께 고친다.

## 구성

| 자리 | 내용 |
|---|---|
| `scripts/` | 내려받기(`download.sh`)와 계산 스크립트 |
| `inputs/` | 내려받은 원자료. git에 올리지 않는다(`.gitignore`). 체크섬은 `docs/input-sha256.txt` |
| `results/` | 스크립트가 만든 결과. 커밋한다 |
| `docs/` | 입력 체크섬, 문헌 목록, 손으로 옮긴 자료(`paleoatlas_sea_levels.csv`) |
| `devlog/` | 그때의 판단과 근거 |

## devlog

- 파일 이름은 `devlog/YYYYMMDD_{nnn}_{title}.md`, 계획은 `devlog/YYYYMMDD_P{nn}_{title}.md`다. `title`은 영어 snake_case로 쓴다.
- 번호는 저장소 전체에서 이어 센다. 다른 devlog는 링크나 "devlog 001"로 가리킨다.
- 새 파일을 만들면 [devlog/README.md](devlog/README.md) 색인에 한 줄을 더한다.
- HANDOFF.md에는 지금 상태만 적는다. 지난 일은 devlog에 남긴다. TODOs.md에서도 끝난 일은 지운다.

## 커밋

- 메시지는 무엇을 했는지 한국어 평서문으로 쓰고, 관련 devlog 번호를 붙인다(예: `PaleoDEM 전 시점 수심값 빈도표를 만든다 (002)`).
- 한 단계가 끝날 때마다 커밋한다. 결과 파일은 그것을 만든 스크립트 변경과 같은 커밋에 넣는다.
- 문서만 고치는 커밋은 `main`에 바로 올린다.
