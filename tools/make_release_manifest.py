"""Write the update manifest for a release folder (size and SHA-256 of each client file).

    python tools/make_release_manifest.py --root release --version 0.13.0 --out release/version.json manifest.json
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

FILES = {
    "LAIN.exe": "LAIN.exe",
    "Game/LAIN-Game.exe": "LAIN-Game.exe",
    "Game/LAIN-Game.pck": "LAIN-Game.pck",
    "LEEME.txt": "LEEME.txt",
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    files = {}
    for path, asset in FILES.items():
        local = args.root / path
        if not local.is_file():
            raise SystemExit(f"Falta {local}")
        files[path] = {"asset": asset, "sha256": digest(local), "size": local.stat().st_size}
    manifest = {"version": args.version, "tag": "v" + args.version, "files": files}
    # Exactly what every launcher will accept.
    spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "packaging" / "updater.py")
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    updater.validate_manifest(manifest)
    for out in args.out:
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
