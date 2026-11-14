# shallowsea

캄브리아기와 판게아 시기의 얕은 바다 면적을 PALEOMAP에서 재계산하고, 지각 면적·부피와 등압평형을 적용했을 때 그 수심 분포가 재현되는지 검증하는 프로젝트.

- [현재 상태와 함정](HANDOFF.md), [할 일](TODOs.md), [진행 기록](devlog/README.md), [문헌](docs/references.md)
- [109개 시점의 CRUST1.0–PaleoDEM 중첩 결과](results/PALEOMAP_CRUST1_0-540Ma.csv)
- [Airy 등압평형 민감도 실험](results/airy_sensitivity.txt)
- [PaleoDEM 원본의 수심 빈도 검사](results/depth_audit.txt)

## 재현

Python 3.13(pyGPlates 1.0.0의 wheel은 cp38–cp313까지만 있어 3.14에는 설치되지 않는다), GDAL의 `gdal_translate`(NetCDF 드라이버 포함), curl, unzip이 필요하다. 최초 실행에서 공개 원본 자료를 내려받는다.

```bash
uv venv --python 3.13 .venv   # uv가 없으면 python3.13 -m venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt   # 또는 python -m pip install -r requirements.txt
bash scripts/download.sh
sha256sum -c docs/input-sha256.txt
python scripts/reconstruct.py
python scripts/airy_sensitivity.py > results/airy_sensitivity.txt
python scripts/depth_audit.py > results/depth_audit.txt
```

커밋된 결과(3e390d2)는 NumPy 2.3.5, pyGPlates 1.0.0, GDAL 3.10.3에서 만들었다. m710q에서 Python 3.13.17, NumPy 2.5.4, pyGPlates 1.0.0, GDAL 3.12.2로 다시 돌려 같은 결과를 얻었다(2026-11-14, [devlog 002](devlog/20261114_002_reproduce_on_m710q.md)). `airy_sensitivity.txt` 첫 줄의 합계 두 개는 마지막 자리가 다르게 나온다. 원자료와 인용은 [docs/references.md](docs/references.md)를 참조한다.
