"""Keep the exported client's reviewed catalogues identical to the server's (English, Russian)."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ru")
SOURCES = {lang: ROOT / f"server/content/i18n/{lang}.json" for lang in LANGUAGES}
TARGETS = {lang: ROOT / f"client/translations/{lang}.json" for lang in LANGUAGES}
SOURCE, TARGET = SOURCES["en"], TARGETS["en"]


def validate(lang="en"):
    catalogue = json.loads(SOURCES[lang].read_text(encoding="utf-8"))
    for source, target in catalogue.items():
        assert isinstance(target, str) and target, f"Empty translation: {source!r}"
        for pattern in (r"\{\w+\}", r"%[-+0-9.]*[sdf]"):
            assert sorted(re.findall(pattern, source)) == sorted(re.findall(pattern, target)), \
                f"Changed placeholders ({lang}): {source!r}"
    return catalogue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for lang in LANGUAGES:
        if not SOURCES[lang].exists():
            continue
        catalogue = validate(lang)
        if args.check:
            assert TARGETS[lang].read_bytes() == SOURCES[lang].read_bytes(), "Run tools/sync_translations.py"
        else:
            TARGETS[lang].parent.mkdir(exist_ok=True)
            TARGETS[lang].write_bytes(SOURCES[lang].read_bytes())
        print(f"ES/{lang.upper()}: {len(catalogue)} reviewed entries; client/server catalogues identical")
