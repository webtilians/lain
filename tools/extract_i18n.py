"""Inventory source strings for the reviewed Spanish/English catalogue.

Never contacts a translation service. f-string values become positional
placeholders so their original spelling (names, IDs, evidence) is preserved.
"""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(?:para|del|que|una|con|puede|puedes|tienes|Guardar|Salir|Volver|Entrar|Nombre|No|El|La|los|las)\b")


def inventory():
    entries = {}
    for path in (ROOT / "server/world_core").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        def visit(node):
            value = None
            if isinstance(node, ast.JoinedStr):
                pieces, index = [], 0
                for part in node.values:
                    if isinstance(part, ast.Constant):
                        pieces.append(part.value)
                    else:
                        pieces.append("{v" + str(index) + "}")
                        index += 1
                value = "".join(pieces)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
            if value is not None:
                if SPANISH.search(value):
                    entries.setdefault(value, []).append(str(path.relative_to(ROOT)))
                return
            for child in ast.iter_child_nodes(node):
                visit(child)
        visit(tree)
    for path in (ROOT / "client/scripts").rglob("*.gd"):
        for raw in re.findall(r'"((?:[^"\\]|\\.)*)"', path.read_text(encoding="utf-8-sig")):
            try:
                value = json.loads('"' + raw + '"')
            except ValueError:
                continue
            if SPANISH.search(value):
                entries.setdefault(value, []).append(str(path.relative_to(ROOT)))
    return entries


if __name__ == "__main__":
    destination = ROOT / "outputs/i18n-inventory.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(inventory(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(destination)
