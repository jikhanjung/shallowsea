#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p inputs
cd inputs
earthbyte=https://www.earthbyte.org/webdav/ftp
crust=https://igppweb.ucsd.edu/~gabi/crust1
download() {
    local url="$1" target="$2"
    if [[ ! -s "$target" ]]; then
        curl --fail --location --retry 2 -A "shallowsea-research-script" "$url" -o "$target.part"
        mv "$target.part" "$target"
    fi
}
download "$earthbyte/Data_Collections/Scotese_Wright_2018_PaleoDEM/Scotese_Wright_2018_Maps_1-88_1degX1deg_PaleoDEMS_nc.zip" dem.zip
download "$earthbyte/earthbyte/Scotese_PaleoAtlas_v3.zip" plates.zip
download "$crust/crust1.0.tar.gz" crust1.0.tar.gz
download "$crust/crust1.0-addon.tar.gz" crust1.0-addon.tar.gz
download "$crust/crsthk.xyz.zip" crust-thick.zip
# Zenodo 10.5281/zenodo.5460860: 0.1° PaleoDEM, 방법 보고서, PaleoAtlas 지도 (devlog 003).
# 이 기록의 1° zip과 Scotese_PaleoAtlas_v3.zip은 위 EarthByte 파일과 md5가 같다.
zenodo=https://zenodo.org/api/records/5460860/files
download "$zenodo/Scotese_Wright_2018_Maps_1-88_6minX6min_PaleoDEMS_nc.zip/content" dem_6min.zip
download "$zenodo/Scotese_Wright2018_PALEOMAP_PaleoDEMs.pdf/content" paleodem_report.pdf
download "$zenodo/PALEOMAP_PaleoAtlases.zip/content" paleoatlases.zip
# van der Meer et al. (2022) 본문(CC BY 4.0)과 부록 1(해수면 곡선, devlog 009).
mkdir -p literature
download "https://eprints.whiterose.ac.uk/id/eprint/189833/7/1-s2.0-S1342937X22002192-main.pdf" literature/vandermeer2022.pdf
download "https://ars.els-cdn.com/content/image/1-s2.0-S1342937X22002192-mmc1.xlsx" literature/vandermeer2022_mmc1.xlsx
# 현재 대륙 잔차 지형(Stephenson et al. 2024, CC BY 4.0, devlog 015).
mkdir -p residual
download "https://zenodo.org/api/records/10633081/files/sstephenson2/global-residual-topography-v1.0.1.zip/content" residual/global-residual-topography-v1.0.1.zip
# Macrostrat 북미(project 1) 단위와 단면 (devlog 006). 계속 갱신되는 자료라 받은 날짜의 체크섬은
# docs/macrostrat-sha256.txt에 따로 둔다. 다시 받으면 값이 달라질 수 있다.
mkdir -p macrostrat
download "https://macrostrat.org/api/v2/units?project_id=1&response=long" macrostrat/units_project1.json
download "https://macrostrat.org/api/v2/columns?project_id=1&response=long&format=geojson_bare" macrostrat/columns_project1.geojson
download "https://macrostrat.org/api/v2/units?project_id=8&response=long" macrostrat/units_project8.json
download "https://macrostrat.org/api/v2/columns?project_id=8&response=long&format=geojson_bare" macrostrat/columns_project8.geojson
download "https://macrostrat.org/api/v2/units?project_id=8&response=long" macrostrat/units_project8.json
download "https://macrostrat.org/api/v2/columns?project_id=8&response=long&format=geojson_bare" macrostrat/columns_project8.geojson
unzip -jo plates.zip '*PlateModel.rot' '*PlatePolygons.gpml'
