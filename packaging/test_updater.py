"""Self-update: only GitHub, only listed files, nothing replaced unless every hash matches."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


updater = load("updater.py")
launcher = load("launcher.py")
RELEASES = "https://github.com/webtilians/lain/releases"


def entry(data: bytes, asset: str) -> dict:
    return {"asset": asset, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def manifest(files: dict, version="0.13.0") -> dict:
    return updater.validate_manifest({"version": version, "tag": "v" + version, "files": files})


class FakeGitHub:
    def __init__(self, assets: dict):
        self.assets = assets
        self.urls = []

    def __call__(self, url, timeout):
        updater.check_url(url)
        self.urls.append(url)
        return io.BytesIO(self.assets[url.rsplit("/", 1)[1]])


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "Game").mkdir()
        (self.root / "Game" / "LAIN-Game.exe").write_bytes(b"engine-1")
        (self.root / "Game" / "LAIN-Game.pck").write_bytes(b"content-1")
        (self.root / "LAIN.exe").write_bytes(b"launcher-1")

    def tearDown(self):
        self.temp.cleanup()

    def release(self, pck=b"content-2", launcher_bytes=b"launcher-1"):
        assets = {"LAIN-Game.exe": b"engine-1", "LAIN-Game.pck": pck, "LAIN.exe": launcher_bytes}
        files = {"Game/LAIN-Game.exe": entry(assets["LAIN-Game.exe"], "LAIN-Game.exe"),
                 "Game/LAIN-Game.pck": entry(b"content-2", "LAIN-Game.pck"),
                 "LAIN.exe": entry(launcher_bytes, "LAIN.exe")}
        return manifest(files), FakeGitHub(assets)

    def test_only_changed_files_are_downloaded_and_swapped(self):
        release, github = self.release()
        self.assertEqual(updater.plan(self.root, release), ["Game/LAIN-Game.pck"])
        self.assertFalse(updater.update(self.root, RELEASES, release, opener=github))
        self.assertEqual((self.root / "Game" / "LAIN-Game.pck").read_bytes(), b"content-2")
        self.assertEqual(github.urls, [RELEASES + "/download/v0.13.0/LAIN-Game.pck"])
        self.assertEqual(updater.installed_version(self.root), "0.13.0")
        self.assertFalse((self.root / ".update").exists())

    def test_a_tampered_download_changes_nothing(self):
        release, github = self.release(pck=b"content-X")
        with self.assertRaises(updater.UpdateError):
            updater.update(self.root, RELEASES, release, opener=github)
        self.assertEqual((self.root / "Game" / "LAIN-Game.pck").read_bytes(), b"content-1")
        self.assertEqual(updater.installed_version(self.root), "")

    def test_new_launcher_is_renamed_in_not_overwritten(self):
        release, github = self.release(launcher_bytes=b"launcher-2")
        self.assertTrue(updater.update(self.root, RELEASES, release, opener=github))
        self.assertEqual((self.root / "LAIN.exe").read_bytes(), b"launcher-2")
        self.assertEqual((self.root / "LAIN.old.exe").read_bytes(), b"launcher-1")
        updater.cleanup(self.root)
        self.assertFalse((self.root / "LAIN.old.exe").exists())

    def test_manifest_cannot_name_other_files_or_bad_hashes(self):
        good = entry(b"x", "x.bin")
        for files in ({"../evil.exe": good}, {"Server/LainServer.exe": good},
                      {"Game/LAIN-Game.pck": dict(good, sha256="nothex"), "Game/LAIN-Game.exe": good},
                      {"Game/LAIN-Game.pck": dict(good, asset="../x"), "Game/LAIN-Game.exe": good},
                      {"Game/LAIN-Game.pck": good}):
            with self.assertRaises(updater.UpdateError):
                manifest(files)

    def test_downloads_only_from_github_over_https(self):
        for url in ("http://github.com/x", "https://evil.example/x", "https://github.com.evil.example/x",
                    "https://user:pw@github.com/x"):
            with self.assertRaises(updater.UpdateError):
                updater.check_url(url)
        handler = updater._GitHubOnly()
        with self.assertRaises(updater.UpdateError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/payload")
        updater.check_url("https://release-assets.githubusercontent.com/github-production-release-asset/1")

    def test_fetch_manifest_reads_the_latest_release(self):
        release, _ = self.release()
        seen = []

        def opener(url, timeout):
            seen.append(url)
            return io.BytesIO(json.dumps(release).encode())

        self.assertEqual(updater.fetch_manifest(RELEASES, opener=opener)["version"], "0.13.0")
        self.assertEqual(seen, [RELEASES + "/latest/download/manifest.json"])


class UniversalLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def test_shared_configuration_is_validated(self):
        self.assertIsNone(launcher.universal_configuration(self.root))
        self.write("lain-server.json", {"server_url": "https://1-2-3-4.sslip.io", "releases": RELEASES + "/"})
        self.assertEqual(launcher.universal_configuration(self.root),
                         {"server_url": "https://1-2-3-4.sslip.io", "releases": RELEASES})
        for bad in ({"server_url": "http://1-2-3-4.sslip.io", "releases": RELEASES},
                    {"server_url": "https://a.example", "releases": "https://evil.example/o/r/releases"},
                    {"server_url": "https://a.example", "releases": RELEASES, "extra": "x"}):
            self.write("lain-server.json", bad)
            with self.assertRaises(ValueError):
                launcher.universal_configuration(self.root)

    def test_environment_passes_version_and_an_old_personal_access(self):
        config = {"server_url": "https://1-2-3-4.sslip.io", "releases": RELEASES}
        (self.root / "version.json").write_text(json.dumps({"version": "0.13.0"}), encoding="utf-8")
        with patch.dict("os.environ", {"LAIN_LLM_API_KEY": "secret", "LAIN_SKIP_MENU": "1"}):
            env = launcher.universal_environment(config, self.root)
        self.assertEqual(env["LAIN_CLIENT_VERSION"], "0.13.0")
        self.assertEqual(env["LAIN_PLAYER_TOKEN"], "")
        self.assertNotIn("LAIN_LLM_API_KEY", env)
        self.assertNotIn("LAIN_SKIP_MENU", env)
        self.write("lain-online.json", {"server_url": "https://1-2-3-4.sslip.io", "player_token": "t" * 43})
        self.assertEqual(launcher.universal_environment(config, self.root)["LAIN_PLAYER_TOKEN"], "t" * 43)

    def test_a_developer_checkout_never_updates_itself(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertFalse(launcher.apply_updates(self.root, RELEASES))


if __name__ == "__main__":
    unittest.main()
