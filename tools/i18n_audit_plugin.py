"""pytest plugin: list player-facing Spanish text that has no English translation.

    LAIN_I18N_AUDIT=outputs/i18n-audit.json python -m pytest -p tools.i18n_audit_plugin -q

With LAIN_I18N_AUDIT_STRICT=1 the run fails when a new text appears that is
neither translated nor listed in tools/i18n_audit_allowlist.json (replies
invented by tests). Every new phase therefore ships in both languages.

Wraps the functions that produce what players read (actions, pages and
snapshots of every system) and records display strings the catalogue cannot
translate. Return values are untouched, so the suite behaves exactly as usual.
"""
import functools
import importlib
import json
import os
import re
from pathlib import Path

SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|que|para|con|una|del|tu|tus|está|hay|puedes|eres|minutos)\b", re.I)
FUNCTIONS = re.compile(r"^(perform_\w+|\w+_snapshot|\w+_projection|talk_to_\w+|reply_to_\w+|start_player_conversation|"
                       r"run_shell|list_player_messages|available_choices|conversation_payload|generate_dialogue_reply)$")
MODULES = ["chapter_one", "network_conflict", "workshop", "cafe_events", "circles", "code_exchange", "layer_three",
           "prologue", "player_conversation", "messages", "residents", "character_sheets", "station_story",
           "station_echo", "wired", "online", "reports", "arcade_catalog", "signal_snake", "code_lab", "player_view"]
found: dict = {}


def _record(value, origin, field=""):
    from server.world_core import i18n

    if isinstance(value, dict):
        for key, item in value.items():
            if key not in i18n.PRIVATE_FIELDS and key not in {"name", "actor_name", "id", "player_name"}:
                _record(item, origin, key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _record(item, origin, field)
    elif hasattr(value, "text") and isinstance(getattr(value, "text"), str):
        _record(value.text, origin, "text")
    elif isinstance(value, str) and field in i18n.DISPLAY_FIELDS:
        probe = value.replace("Café", "").replace("café", "")
        if SPANISH.search(probe) and i18n.t(value, "en") == value:
            found.setdefault(value, origin)


def _wrap(module, name):
    original = getattr(module, name)

    @functools.wraps(original)
    def audited(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            _record(result, f"{module.__name__.rsplit('.', 1)[-1]}.{name}")
        except Exception:  # noqa: BLE001 - auditing must never change a test
            pass
        return result

    setattr(module, name, audited)


def pytest_configure(config):
    if not os.getenv("LAIN_I18N_AUDIT"):
        return
    for short in MODULES:
        try:
            module = importlib.import_module("server.world_core." + short)
        except ImportError:
            continue
        for name in list(vars(module)):
            if FUNCTIONS.match(name) and callable(getattr(module, name)):
                _wrap(module, name)


def pytest_sessionfinish(session, exitstatus):
    target = os.getenv("LAIN_I18N_AUDIT")
    if not target:
        return
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    allowed = set(json.loads(Path(__file__).with_name("i18n_audit_allowlist.json").read_text(encoding="utf-8")))
    new = sorted(set(found) - allowed)
    print(f"\nI18N AUDIT: {len(found)} sin traducir, {len(new)} nuevos -> {target}")
    for text in new:
        print("  SIN TRADUCIR:", repr(text[:120]), "<-", found[text])
    if new and os.getenv("LAIN_I18N_AUDIT_STRICT") == "1":
        session.exitstatus = 1
