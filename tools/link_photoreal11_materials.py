"""Map the named materials of the Visual 0.11 GLBs onto the shared .tres library.

Godot must have imported each GLB once (so the .import file exists). The
script rewrites `_subresources` so every material whose name matches a file in
client/art/photoreal11/materials/ is loaded from that file; reimport afterwards.

    python tools/link_photoreal11_materials.py
"""

import json
import re
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "client"
MATERIALS = CLIENT / "art" / "photoreal11" / "materials"
GLBS = sorted((CLIENT / "art" / "photoreal11").rglob("*.glb"))


def glb_material_names(path: Path) -> list[str]:
    data = path.read_bytes()
    length = int.from_bytes(data[12:16], "little")
    document = json.loads(data[20 : 20 + length])
    return [m["name"] for m in document.get("materials", [])]


def main() -> None:
    library = {p.stem for p in MATERIALS.glob("*.tres")}
    for glb in GLBS:
        settings = glb.with_name(glb.name + ".import")
        if not settings.exists():
            raise SystemExit(f"Import {glb.name} in Godot first")
        mapping = {}
        for name in glb_material_names(glb):
            if name not in library:
                raise SystemExit(f"{glb.name}: no material file for {name!r}")
            path = f"res://art/photoreal11/materials/{name}.tres"
            mapping[name] = {
                "use_external/enabled": True,
                "use_external/fallback_path": path,
                "use_external/path": path,
            }
        text = settings.read_text(encoding="utf-8")
        block = "_subresources=" + json.dumps({"materials": mapping}, indent=0)
        text, count = re.subn(r"^_subresources=.*?(?=^\S+/|\Z)", block + "\n", text, flags=re.S | re.M)
        if count != 1:
            raise SystemExit(f"Unexpected import format in {settings}")
        settings.write_text(text, encoding="utf-8")
        print(f"{glb.name}: {len(mapping)} materials linked")


if __name__ == "__main__":
    main()
