"""List client sentences built by concatenation ("texto " + valor + " más") whose
template ("texto {v0} más") has no entry in the reviewed catalogue.

    python tools/i18n_templates.py            # report
    python tools/i18n_templates.py --json     # untranslated templates as JSON
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPANISH = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]|\b(?:de|del|la|el|los|las|que|con|para|tu|tus|no|es|está|hay|minutos?|mundo)\b", re.I)
LITERAL = r'"(?:[^"\\]|\\.)*"'


def statements(text: str):
    """Join continuation lines so one concatenated expression is one string."""
    buffer = ""
    for line in text.splitlines():
        stripped = line.strip()
        buffer += " " + stripped
        if stripped.endswith(("+", "(", ",")) and not stripped.endswith("),"):
            continue
        yield buffer
        buffer = ""


def templates(expression: str):
    """Every maximal 'literal (+ value + literal)*' chain inside a statement."""
    for chain in re.finditer(LITERAL + r"(?:\s*\+\s*[^+]+?\s*\+\s*" + LITERAL + r"|\s*\+\s*" + LITERAL + r")*(?:\s*\+\s*[\w.\[\]()\"]+)?", expression):
        parts = re.split(r"\s*\+\s*", chain.group(0))
        if len(parts) < 2:
            continue
        out, index = "", 0
        for part in parts:
            if re.fullmatch(LITERAL, part):
                out += json.loads(part)
            else:
                out += "{v" + str(index) + "}"
                index += 1
        if index and SPANISH.search(out):
            yield out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    catalogue = json.loads((ROOT / "server/content/i18n/en.json").read_text(encoding="utf-8"))
    from server.world_core import i18n
    missing = {}
    for path in sorted((ROOT / "client/scripts").rglob("*.gd")):
        for statement in statements(path.read_text(encoding="utf-8-sig")):
            for template in templates(statement):
                probe = re.sub(r"\{v\d+\}", "X1", template)
                if template in catalogue or i18n.t(probe, "en") != probe:
                    continue
                missing.setdefault(template, str(path.relative_to(ROOT)))
    if args.json:
        print(json.dumps(missing, ensure_ascii=False, indent=1))
    else:
        for template, where in missing.items():
            print(f"{where}: {template!r}")
        print(len(missing), "plantillas sin traducir")


if __name__ == "__main__":
    main()
