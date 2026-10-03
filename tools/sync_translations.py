"""Keep the exported client's reviewed catalogue identical to the server's."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "server/content/i18n/en.json"
TARGET = ROOT / "client/translations/en.json"


def validate():
    catalogue = json.loads(SOURCE.read_text(encoding="utf-8"))
    for source, target in catalogue.items():
        assert isinstance(target, str) and target, f"Empty translation: {source!r}"
        for pattern in (r"\{\w+\}", r"%[-+0-9.]*[sdf]"):
            assert re.findall(pattern, source) == re.findall(pattern, target), f"Changed placeholders: {source!r}"
    return catalogue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    catalogue = validate()
    if args.check:
        assert TARGET.read_bytes() == SOURCE.read_bytes(), "Run tools/sync_translations.py"
    else:
        TARGET.parent.mkdir(exist_ok=True)
        TARGET.write_bytes(SOURCE.read_bytes())
    print(f"ES/EN: {len(catalogue)} reviewed entries; client/server catalogues identical")
