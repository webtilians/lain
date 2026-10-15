"""The download page shows real game text: tools/landing_inputs.py plays it with the server's code."""
import json

from tools import landing_inputs

FLAGS = ("LAIN_WORLD_DB", "LAIN_LAYER_ONE", "LAIN_LAYER_THREE", "LAIN_PROLOGUE_ENABLED",
         "LAIN_CITY_RESIDENTS_ENABLED", "LAIN_CORPORATION", "LAIN_LLM_ENABLED")


def test_the_oscilloscope_and_ryokos_first_words_come_from_the_game(monkeypatch, tmp_path):
    for flag in FLAGS:  # put back after the test whatever the tool sets
        monkeypatch.setenv(flag, "")
    assert landing_inputs.main([str(tmp_path)]) == 0
    session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert session[0]["command"].startswith("scope ") and "osciloscopio" in session[0]["output"]
    assert session[0]["output"].count("¯") > 40 and session[0]["hostname"]
    ryoko = json.loads((tmp_path / "ryoko.json").read_text(encoding="utf-8"))["INTRO"]
    assert ryoko["speaker"] == "Ryoko" and "profesor" in ryoko["text"] and len(ryoko["choices"]) >= 3
