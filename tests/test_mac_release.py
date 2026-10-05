"""The Mac app's release.json and the check of its exported ZIP."""
import json
import plistlib
import stat
import zipfile

import pytest

from tools import mac_release

APP = mac_release.APP


def entry(archive, name, data=b"", mode=0o644):
    info = zipfile.ZipInfo(name)
    info.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(info, data)


def mac_zip(path, *, executable=True, name="Sesion Cero", signed=True, version="0.28.0", pck=True):
    plist = plistlib.dumps({"CFBundleExecutable": "Sesion Cero", "CFBundleName": name, "CFBundleShortVersionString": version,
                            "CFBundleIdentifier": mac_release.BUNDLE_ID})
    with zipfile.ZipFile(path, "w") as archive:
        entry(archive, f"{APP}/Contents/Info.plist", plist)
        entry(archive, f"{APP}/Contents/MacOS/Sesion Cero", b"\xcf\xfa\xed\xfe", 0o755 if executable else 0o644)
        if pck:
            entry(archive, f"{APP}/Contents/Resources/Sesion Cero.pck", b"GDPC" * 1000)
        if signed:
            entry(archive, f"{APP}/Contents/_CodeSignature/CodeResources", b"<plist/>")
    return path


def test_release_json_carries_the_shared_server_and_the_downloads(tmp_path):
    target = tmp_path / "release.json"
    data = mac_release.info("0.28.0", target)
    shared = json.loads((mac_release.ROOT / "packaging" / "lain-server.json").read_text(encoding="utf-8"))
    assert json.loads(target.read_text(encoding="utf-8")) == data
    assert data["server_url"] == shared["server_url"] and data["version"] == "0.28.0"
    assert data["manifest"] == shared["releases"] + "/latest/download/manifest.json"
    assert data["downloads"]["macOS"].endswith("/latest/download/SesionCero-Mac.zip")
    assert data["downloads"]["Windows"].endswith("/latest/download/LAIN-Windows.zip")
    assert all(url.startswith("https://") for url in [data["server_url"], data["page"], *data["downloads"].values()])


def test_a_whole_app_passes(tmp_path):
    found = mac_release.check(mac_zip(tmp_path / "ok.zip"), "0.28.0")
    assert found["name"] == "Sesion Cero" and found["version"] == "0.28.0"
    assert found["program"] == f"{APP}/Contents/MacOS/Sesion Cero"


@pytest.mark.parametrize("broken, reason", [
    ({"executable": False}, "not executable"),
    ({"name": "LAIN"}, "Wrong app name"),
    ({"signed": False}, "not signed"),
    ({"pck": False}, "game data"),
    ({"version": "0.0.0"}, "Wrong version"),
])
def test_a_broken_export_fails(tmp_path, broken, reason):
    with pytest.raises(SystemExit, match=reason):
        mac_release.check(mac_zip(tmp_path / "broken.zip", **broken), "0.28.0")
