"""Portable distribution tests; no Godot, network service or real SQLite involved."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent


def load_script(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


launcher = load_script("launcher.py")
check_zip = load_script("check_zip.py")


class Beta01PackagingTests(unittest.TestCase):
    def test_local_save_is_forced_outside_developer_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {
                "LAIN_WORLD_DB": "C:/Users/developer/lain/world.db",
                "LAIN_LLM_API_KEY": "secret-not-for-release",
                "LAIN_LLM_ALLOW_REMOTE": "1",
                "LAIN_ARCADE_CATALOG_PATH": "C:/private/catalog.json",
            }):
                environment = launcher.server_environment(Path(temporary), False)
            self.assertEqual(environment["LAIN_WORLD_DB"], str((Path(temporary) / "save.db").resolve()))
            self.assertEqual(environment["LAIN_LLM_ENABLED"], "0")
            self.assertEqual(environment["LAIN_LLM_API_KEY"], "")
            self.assertEqual(environment["LAIN_LLM_ALLOW_REMOTE"], "0")
            self.assertNotIn("LAIN_ARCADE_CATALOG_PATH", environment)
            self.assertEqual(environment["LAIN_PROLOGUE_ENABLED"], "1")
            self.assertEqual(environment["LAIN_CODE_EXCHANGE"], "1")

    def test_opt_in_ai_is_only_local(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = launcher.server_environment(Path(temporary), True)
            self.assertEqual(environment["LAIN_LLM_ENABLED"], "1")
            self.assertEqual(environment["LAIN_LLM_MODEL"], "lain-qwen7b")
            self.assertEqual(environment["LAIN_LLM_ENDPOINT"], "http://127.0.0.1:11434/v1/chat/completions")
            self.assertEqual(environment["LAIN_LLM_ALLOW_REMOTE"], "0")

    def test_local_model_absent_without_ollama(self):
        with patch.object(launcher, "urlopen", side_effect=OSError("offline")):
            self.assertFalse(launcher.local_model_available())

    def _zip(self, path, extra=None, drop=None):
        entries = {name: b"example" for name in check_zip.REQUIRED}
        entries.pop("LEEME.txt", None)
        entries["LEEME.txt"] = b"Public beta only"
        if drop:
            entries.pop(drop)
        entries.update(extra or {})
        with ZipFile(path, "w") as output:
            for name, body in entries.items():
                output.writestr(name, body)

    def test_complete_safe_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "release.zip"
            self._zip(target)
            check_zip.verify(target)

    def test_zip_rejects_private_world(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "release.zip"
            self._zip(target, {"Server/world.db": b"private"})
            with self.assertRaisesRegex(ValueError, "Unsafe entry"):
                check_zip.verify(target)

    def test_zip_rejects_dot_env(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "release.zip"
            self._zip(target, {"Server/.env.production": b"api key"})
            with self.assertRaisesRegex(ValueError, "Unsafe entry"):
                check_zip.verify(target)

    def test_zip_requires_godot_game_and_pck(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "release.zip"
            self._zip(target, drop="Game/LAIN-Game.pck")
            with self.assertRaisesRegex(ValueError, "Missing output"):
                check_zip.verify(target)


if __name__ == "__main__":
    unittest.main()
