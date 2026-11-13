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
unzip -jo plates.zip '*PlateModel.rot' '*PlatePolygons.gpml'
