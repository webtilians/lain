"""The Mac app: what it carries inside and a check of the exported ZIP.

The Windows download has a launcher that tells the game which server to use,
which version it is, and updates it. The Mac app is the Godot game alone, so
it carries that in res://release.json:

    python tools/mac_release.py info --version 0.28.0       # writes client/release.json
    python tools/mac_release.py check SesionCero-Mac.zip     # fails on a broken export

`check` makes sure the ZIP holds a whole .app: the program with its executable
bit (a ZIP rebuilt on Windows loses it and macOS then calls the app damaged),
the game data, and an Info.plist with the right name, identifier and version.
"""

import argparse
import json
import plistlib
import stat
import sys
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
# No accent in file names inside the bundle: Godot's ad-hoc seal of «Sesión Cero» does not verify
# on a Mac. The window still says «Sesión Cero» (the game sets its title).
APP = "Sesion Cero.app"
BUNDLE_ID = "io.github.webtilians.sesioncero"
ZIP_NAME = "SesionCero-Mac.zip"


def info(version: str, target: Path = ROOT / "client" / "release.json") -> dict:
    shared = json.loads((ROOT / "packaging" / "lain-server.json").read_text(encoding="utf-8"))
    releases = shared["releases"].rstrip("/")
    data = {
        "server_url": shared["server_url"].rstrip("/"),
        "version": version,
        "manifest": f"{releases}/latest/download/manifest.json",
        "downloads": {"macOS": f"{releases}/latest/download/{ZIP_NAME}",
                      "Windows": f"{releases}/latest/download/LAIN-Windows.zip"},
        "page": shared["server_url"].rstrip("/"),
    }
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def check(path: Path, version: str | None = None) -> dict:
    with zipfile.ZipFile(path) as archive:
        entries = {item.filename: item for item in archive.infolist()}
        apps = sorted({name.split("/", 1)[0] for name in entries if ".app/" in name})
        if apps != [APP]:
            raise SystemExit(f"Expected only {APP!r} in the ZIP, found {apps}")
        plist = plistlib.loads(archive.read(f"{APP}/Contents/Info.plist"))
        program = f"{APP}/Contents/MacOS/{plist['CFBundleExecutable']}"
        if program not in entries:
            raise SystemExit(f"Missing the program {program}")
        mode = entries[program].external_attr >> 16
        if not mode & stat.S_IXUSR:
            raise SystemExit(f"{program} is not executable (mode {oct(mode)})")
        packs = [name for name in entries if name.startswith(f"{APP}/Contents/Resources/") and name.endswith(".pck")]
        if not packs:
            raise SystemExit("Missing the game data (.pck)")
        if f"{APP}/Contents/_CodeSignature/CodeResources" not in entries:
            raise SystemExit("The app is not signed (an unsigned app does not open on Apple silicon)")
    found = {"name": plist.get("CFBundleName"), "identifier": plist.get("CFBundleIdentifier"),
             "version": plist.get("CFBundleShortVersionString"), "program": program,
             "data_mb": round(sum(entries[name].file_size for name in packs) / 1e6),
             "zip_mb": round(path.stat().st_size / 1e6)}
    if found["identifier"] != BUNDLE_ID:
        raise SystemExit(f"Wrong bundle identifier: {found['identifier']}")
    if found["name"] != APP.removesuffix(".app"):
        raise SystemExit(f"Wrong app name: {found['name']}")
    if version and found["version"] != version:
        raise SystemExit(f"Wrong version in Info.plist: {found['version']} (expected {version})")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("info")
    write.add_argument("--version", required=True)
    verify = commands.add_parser("check")
    verify.add_argument("zip", type=Path)
    verify.add_argument("--version")
    args = parser.parse_args()
    if args.command == "info":
        print(json.dumps(info(args.version), ensure_ascii=False))
    else:
        print(json.dumps(check(args.zip, args.version), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
