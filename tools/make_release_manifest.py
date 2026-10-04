"""Write the update manifest for a release folder (size and SHA-256 of each client file).

    python tools/make_release_manifest.py --root release --version 0.13.0 --parts parts.json.gz \
        --out release/version.json manifest.json

--parts also writes the patch list: every big file cut into content-defined
parts, so installed launchers download only the parts they do not have.
"""

import argparse
import gzip
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
PATCH_FROM = 1_000_000  # smaller files are simply downloaded again


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def load_updater():
    spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "packaging" / "updater.py")
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    return updater


def write_parts(root: Path, target: Path, updater) -> dict:
    """The same cut every launcher makes of its own copy (updater.split)."""
    table = {path: [[length, part] for _, length, part in updater.split(root / path)]
             for path in FILES if (root / path).stat().st_size >= PATCH_FROM}
    raw = json.dumps(table, separators=(",", ":")).encode("utf-8")
    target.write_bytes(gzip.compress(raw, mtime=0))
    return {"asset": target.name, "sha256": digest(target), "size": target.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parts", type=Path, help="write the patch list here (a release asset)")
    parser.add_argument("--out", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    files = {}
    for path, asset in FILES.items():
        local = args.root / path
        if not local.is_file():
            raise SystemExit(f"Falta {local}")
        files[path] = {"asset": asset, "sha256": digest(local), "size": local.stat().st_size}
    manifest = {"version": args.version, "tag": "v" + args.version, "files": files}
    updater = load_updater()
    if args.parts:
        manifest["parts"] = write_parts(args.root, args.parts, updater)
    # Exactly what every launcher will accept.
    updater.validate_manifest(manifest)
    for out in args.out:
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
