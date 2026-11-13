# shallowsea

캄브리아기와 판게아 시기의 얕은 바다 면적을 PALEOMAP에서 재계산하고, 지각 면적·부피와 등압평형을 적용했을 때 그 수심 분포가 재현되는지 검증하는 프로젝트.

- [연구 배경, 진행 기록, 다음 검증](docs/handoff.md)
- [109개 시점의 CRUST1.0–PaleoDEM 중첩 결과](results/PALEOMAP_CRUST1_0-540Ma.csv)
- [Airy 등압평형 민감도 실험](results/airy_sensitivity.txt)
- [PaleoDEM 원본의 수심 빈도 검사](results/depth_audit.txt)

## 재현

Python 3.12, GDAL의 `gdal_translate`(NetCDF 드라이버 포함), curl, unzip이 필요하다. 최초 실행에서 공개 원본 자료를 내려받는다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash scripts/download.sh
sha256sum -c docs/input-sha256.txt
python scripts/reconstruct.py
python scripts/airy_sensitivity.py > results/airy_sensitivity.txt
python scripts/depth_audit.py > results/depth_audit.txt
```

재현 환경은 NumPy 2.3.5, pyGPlates 1.0.0, GDAL 3.10.3이었다. 원자료와 인용은 인계 문서를 참조한다.
