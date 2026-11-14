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
        curl --fail --location --retry 2 "$url" -o "$target.part"
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
unzip -jo plates.zip '*PlateModel.rot' '*PlatePolygons.gpml'
