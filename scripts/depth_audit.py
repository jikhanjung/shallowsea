"""Report global PaleoDEM depth modes and their area by latitude band."""
import io
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AGES = {0, 240, 260, 420, 500, 535}
with zipfile.ZipFile(ROOT / "inputs/dem.zip") as archive, tempfile.TemporaryDirectory() as tmp:
    for name in sorted(archive.namelist()):
        match = re.search(r"_(\d+)Ma\.nc$", name)
        if not match or int(match[1]) not in AGES:
            continue
        grid_file = Path(tmp) / "depth.nc"
        grid_file.write_bytes(archive.read(name))
        lon, lat, height = np.loadtxt(io.BytesIO(subprocess.check_output(
            ["gdal_translate", "-q", "-of", "XYZ", str(grid_file), "/vsistdout/"]
        ))).reshape(181, 361, 3).transpose(2, 0, 1)
        assert np.allclose(height[:, 0], height[:, -1])
        bounds = np.deg2rad(np.clip(np.stack([lat - .5, lat + .5]), -90, 90))
        area = 6371.0088**2 * np.deg2rad(1) * np.diff(np.sin(bounds), axis=0)[0]
        area[:, [0, -1]] *= .5
        assert np.isclose(area.sum(), 4 * np.pi * 6371.0088**2)
        band = (height < -150) & (height >= -200)
        depths, indices = np.unique(-height[band], return_inverse=True)
        by_depth = np.bincount(indices, weights=area[band]) / 1e6
        print(f"{match[1]} Ma | area in million km²")
        print(f"  150–200 m: {by_depth.sum():.3f}")
        for i in np.argsort(by_depth)[-5:][::-1]:
            print(f"  exactly {depths[i]:g} m: {by_depth[i]:.3f}")
        for lo in range(-90, 90, 30):
            mask = (lat >= lo) & ((lat < lo + 30) | (lat == 90))
            print(f"  latitude [{lo}, {lo + 30}]: {area[band & mask].sum()/1e6:.3f}")
