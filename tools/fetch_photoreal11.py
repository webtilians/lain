"""Download the CC0 Poly Haven sources used by Visual 0.11 (photoreal street).

Raw downloads go to a folder outside the repository (default
%USERPROFILE%/lain-assets/photoreal11). Optimised copies are committed under
client/art/photoreal11; this script only makes the sources reproducible.

Every file is checked against the MD5 published by the Poly Haven API and
recorded in manifest.json next to the downloads.

    python tools/fetch_photoreal11.py [--dest DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
UA = {"User-Agent": "LAIN-photoreal11-fetch/1.0"}

# Surfaces seen at full screen size keep 2K; props use 1K.
TEXTURES_2K = [
    "concrete_block_wall",
    "grey_roof_tiles_02",
    "beige_wall_001",
    "grey_plaster_02",
    "japanese_cedar_planks",
    "painted_metal_shutter",
    "asphalt_02",
    "concrete_pavement",
    "corrugated_iron",
    "exterior_wall_cladding_03",
]
TEXTURE_MAPS = ("Diffuse", "nor_gl", "arm")
MODELS_1K = [
    "modular_electricity_poles",
    "modular_electric_cables",
    "modular_metal_gutter",
    "utility_box_01",
    "utility_box_02",
    "street_lamp_02",
    "security_light",
    "metal_trash_can",
    "water_manhole_cover",
    "rollershutter_window_01",
    "rollershutter_door",
    "shrub_01",
    "shrub_02",
    "shrub_04",
    "potted_plant_01",
    "potted_plant_02",
    "planter_box_01",
    "island_tree_02",
]
HDRIS_2K = ["qwantani_late_afternoon_puresky"]


def get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        return json.load(r)


def download(url: str, target: Path, md5: str, manifest: list) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and hashlib.md5(target.read_bytes()).hexdigest() == md5:
        status = "cached"
    else:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
            data = r.read()
        actual = hashlib.md5(data).hexdigest()
        if actual != md5:
            raise SystemExit(f"MD5 mismatch for {url}: {actual} != {md5}")
        target.write_bytes(data)
        status = "downloaded"
    manifest.append({"url": url, "file": target.as_posix(), "md5": md5})
    print(f"{status:10s} {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("USERPROFILE", Path.home())) / "lain-assets" / "photoreal11",
    )
    dest = parser.parse_args().dest.resolve()
    manifest: list[dict] = []

    for asset in TEXTURES_2K:
        files = get_json(f"{API}/files/{asset}")
        for kind in TEXTURE_MAPS:
            entry = files[kind]["2k"]["jpg"]
            download(entry["url"], dest / "textures" / asset / Path(entry["url"]).name, entry["md5"], manifest)

    for asset in MODELS_1K:
        gltf = get_json(f"{API}/files/{asset}")["gltf"]["1k"]["gltf"]
        root = dest / "models" / asset
        download(gltf["url"], root / Path(gltf["url"]).name, gltf["md5"], manifest)
        # Included buffers and textures keep their relative paths from the .gltf.
        for relative, entry in gltf.get("include", {}).items():
            download(entry["url"], root / relative, entry["md5"], manifest)

    for asset in HDRIS_2K:
        entry = get_json(f"{API}/files/{asset}")["hdri"]["2k"]["hdr"]
        download(entry["url"], dest / "hdri" / Path(entry["url"]).name, entry["md5"], manifest)

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(Path(m["file"]).stat().st_size for m in manifest)
    print(f"{len(manifest)} files, {total / 1e6:.0f} MB in {dest}")


if __name__ == "__main__":
    main()
