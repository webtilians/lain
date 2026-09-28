"""Portable distribution tests; no Godot, network service or real SQLite involved."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent


def load_script(filename: str):
    spec = importlib.util.spec_from_file_location(
        filename.replace(".", "_"), ROOT / filename
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


launcher = load_script("launcher.py")
check_zip = load_script("check_zip.py")


class Beta01PackagingTests(unittest.TestCase):

    @unittest.skipUnless(os.name == "nt", "Windows launcher locking")
    def test_second_launcher_reports_existing_instance_without_crashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            first = launcher.acquire_lock(data)
            self.assertIsNotNone(first)
            try:
                self.assertIsNone(launcher.acquire_lock(data))
            finally:
                launcher.release_lock(first)
            reopened = launcher.acquire_lock(data)
            self.assertIsNotNone(reopened)
            launcher.release_lock(reopened)

    def test_local_save_is_forced_outside_developer_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {
                    "LAIN_WORLD_DB": "C:/Users/developer/lain/world.db",
                    "LAIN_LLM_API_KEY": "secret-not-for-release",
                    "LAIN_LLM_ALLOW_REMOTE": "1",
                    "LAIN_ARCADE_CATALOG_PATH": "C:/private/catalog.json",
                },
            ):
                environment = launcher.server_environment(Path(temporary), False)
            self.assertEqual(
                environment["LAIN_WORLD_DB"],
                str((Path(temporary) / "save.db").resolve()),
            )
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
            self.assertEqual(
                environment["LAIN_LLM_ENDPOINT"],
                "http://127.0.0.1:11434/v1/chat/completions",
            )
            self.assertEqual(environment["LAIN_LLM_ALLOW_REMOTE"], "0")

    def test_local_model_absent_without_ollama(self):
        with patch.object(launcher, "urlopen", side_effect=OSError("offline")):
            self.assertFalse(launcher.local_model_available())

    def test_relay_mode_has_no_provider_key_and_uses_existing_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {
                    "LAIN_LLM_API_KEY": "private",
                    "LAIN_AI_GATEWAY_URL": "https://wrong.example",
                },
            ):
                environment = launcher.server_environment(
                    Path(temporary), False, "https://lain.example"
                )
            self.assertEqual(environment["LAIN_LLM_ENABLED"], "1")
            self.assertEqual(environment["LAIN_AI_GATEWAY_URL"], "https://lain.example")
            self.assertEqual(environment["LAIN_LLM_API_KEY"], "")
            self.assertEqual(
                environment["LAIN_WORLD_DB"],
                str((Path(temporary) / "save.db").resolve()),
            )
            self.assertEqual(
                environment["LAIN_AI_SESSION_FILE"],
                str((Path(temporary) / "ai-session.json").resolve()),
            )

    def test_offline_mode_does_not_inherit_remote_relay(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {
                    "LAIN_AI_GATEWAY_URL": "https://wrong.example",
                    "LAIN_AI_SESSION_FILE": "private.json",
                },
            ):
                environment = launcher.server_environment(Path(temporary), False)
            self.assertEqual(environment["LAIN_AI_GATEWAY_URL"], "")
            self.assertEqual(environment["LAIN_AI_SESSION_FILE"], "")

    def test_public_configuration_and_optional_empty_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(launcher.shared_ai_url(root), "")
            (root / "lain-ai.json").write_text(
                '{"gateway_url":"https://lain.example/"}'
            )
            self.assertEqual(launcher.shared_ai_url(root), "https://lain.example")
            (root / "lain-ai.json").write_text('{"gateway_url":""}')
            self.assertEqual(launcher.shared_ai_url(root), "")

    def test_rejects_secret_or_insecure_public_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for content in [
                '{"gateway_url":"http://example.com"}',
                '{"gateway_url":"https://example.com?key=secret"}',
                '{"gateway_url":"https://example.com","api_key":"secret"}',
            ]:
                (root / "lain-ai.json").write_text(content)
                with self.assertRaises(ValueError):
                    launcher.shared_ai_url(root)

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

    def test_zip_allows_only_public_ai_url_and_never_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release.zip"
            self._zip(
                target, {"lain-ai.json": b'{"gateway_url":"https://lain.example"}'}
            )
            check_zip.verify(target)
            for extra in [
                {"lain-ai.json": b'{"gateway_url":"","api_key":"secret"}'},
                {"Server/ai-session.json": b"private-session"},
                {"Server/.dev.vars": b"secret"},
            ]:
                self._zip(target, extra)
                with self.assertRaises(ValueError):
                    check_zip.verify(target)

    def test_online_configuration_uses_local_or_https_origin_and_private_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "lain-online.json"
            self.assertIsNone(launcher.online_configuration(root))
            config.write_text('{"server_url":"","player_token":""}')
            self.assertIsNone(launcher.online_configuration(root))
            for url in (
                "https://world.example",
                "http://127.0.0.1:8042",
                "http://192.168.1.5:8000",
                "http://[::1]:8000",
            ):
                config.write_text(
                    json.dumps({"server_url": url, "player_token": "a" * 43})
                )
                self.assertEqual(launcher.online_configuration(root)["server_url"], url)
            for url in (
                "http://world.example",
                "https://secret@world.example",
                "https://world.example?key=secret",
                "https://world.example/route",
                "http://169.254.169.254",
                "https://world.example:0",
            ):
                config.write_text(
                    json.dumps({"server_url": url, "player_token": "a" * 43})
                )
                with self.assertRaises(ValueError):
                    launcher.online_configuration(root)
            for token in ("", "short", "a" * 42 + "\n", "a" * 42 + "é"):
                config.write_text(
                    json.dumps(
                        {"server_url": "https://world.example", "player_token": token}
                    )
                )
                with self.assertRaises(ValueError):
                    launcher.online_configuration(root)

    def test_online_profile_is_separate_and_player_never_receives_provider_credentials(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": temporary,
                "GROQ_API_KEY": "private",
                "LAIN_LLM_API_KEY": "private",
                "OPENAI_API_KEY": "private",
            },
        ):
            a = {"server_url": "https://world.example", "player_token": "a" * 43}
            b = {**a, "player_token": "b" * 43}
            env = launcher.online_environment(a)
            for key in ("GROQ_API_KEY", "LAIN_LLM_API_KEY", "OPENAI_API_KEY"):
                self.assertNotIn(key, env)
            self.assertEqual(env["LAIN_PLAYER_TOKEN"], a["player_token"])
            self.assertNotEqual(launcher.data_directory(a), launcher.data_directory(b))
            self.assertNotEqual(launcher.data_directory(a), launcher.data_directory())
            offline = launcher.server_environment(Path(temporary), False)
            self.assertEqual(offline["LAIN_ONLINE"], "0")
            self.assertEqual(offline["LAIN_PLAYER_TOKEN"], "")

    def test_public_zip_rejects_personal_online_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "release.zip"
            self._zip(
                target, {"lain-online.json": b'{"server_url":"","player_token":""}'}
            )
            check_zip.verify(target)
            self._zip(
                target,
                {
                    "lain-online.json": b'{"server_url":"https://world.example","player_token":"private"}'
                },
            )
            with self.assertRaisesRegex(ValueError, "private access"):
                check_zip.verify(target)


if __name__ == "__main__":
    unittest.main()
