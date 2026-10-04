"""Download the CC0 Poly Haven sources used by Visual 0.12 (gothic night).

Same checks as fetch_photoreal11.py (MD5 from the Poly Haven API, manifest.json)
into %USERPROFILE%/lain-assets/gothic12 by default.

    python tools/fetch_gothic12.py [--dest DIR]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fetch_photoreal11 import API, TEXTURE_MAPS, download, get_json

TEXTURES_2K = [
    "dark_brick_wall",
    "castle_wall_slates",
    "concrete_wall_006",
    "rust_coarse_01",
    "metal_grate_rusty",
    "black_painted_planks",
    "floral_jacquard",
    "leather_red_02",
]
MODELS_1K = ["modular_chainlink_fence"]
HDRIS_2K = ["qwantani_moonrise_puresky"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("USERPROFILE", Path.home())) / "lain-assets" / "gothic12",
    )
    dest = parser.parse_args().dest.resolve()
    manifest: list[dict] = []
    for asset in TEXTURES_2K:
        files = get_json(f"{API}/files/{asset}")
        for kind in TEXTURE_MAPS:
            # Some fabrics ship colour variants (coll1, coll2) instead of Diffuse.
            source = kind if kind in files else "coll1"
            entry = files[source]["2k"]["jpg"]
            name = Path(entry["url"]).name.replace("_coll1_", "_diff_")
            download(entry["url"], dest / "textures" / asset / name, entry["md5"], manifest)
    for asset in MODELS_1K:
        gltf = get_json(f"{API}/files/{asset}")["gltf"]["1k"]["gltf"]
        root = dest / "models" / asset
        download(gltf["url"], root / Path(gltf["url"]).name, gltf["md5"], manifest)
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
