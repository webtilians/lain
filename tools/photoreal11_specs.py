"""Write the Visual 0.11 building specs shared by Blender and Godot.

Reads each cutaway building's plot (bounds) from the district scene, assigns a
building kind, the street it faces and where the game's door is, and writes
client/tools/blender/photoreal11_buildings.json:

  - Blender (jp_block.py) models each spec in its canonical frame;
  - Godot (build_photoreal11.gd) swaps the old box building for the GLB,
    rotated by `rotation_deg` about the plot centre.

    python tools/photoreal11_specs.py
"""

import json
import re
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "client"
SCENE = CLIENT / "art" / "reference09" / "Neighborhood.tscn"
OUT = CLIENT / "tools" / "blender" / "photoreal11_buildings.json"

# Door positions from res://scripts/world/CityLayout.gd (x, z).
DOORS = {
    "BOOKSHOP": (11, 7.75), "GROCERY": (21, 7.25), "VIDEO_CLUB": (18, -45.25),
    "CAFE": (-10, -45.75), "IZAKAYA": (-11, -80.25), "ARCADE": (12, -81.25),
    "APARTMENT": (-12, 7.7), "SCHOOL": (-18, -20.8), "NIGHTCLUB": (25.15, -65),
    "STATION": (0, -106.5),
}

# node: (kind, facing, door, wall, extras)
PLAN = {
    "Apartments": ("apato", "-Z", "APARTMENT", "wall_siding", {}),
    "CornerBooks": ("shop", "+Z", "BOOKSHOP", "wall_mortar", {"awning": "awning_green"}),
    "Grocer": ("shop", "+Z", "GROCERY", "wall_siding", {"awning": "awning_red"}),
    "Residence02": ("house1", "+X", None, "wall_mortar", {}),
    "School": ("school", "+Z", "SCHOOL", "wall_mortar", {}),
    "Arcade": ("shop", "+Z", "VIDEO_CLUB", "wall_siding", {"awning": "awning_blue", "sign": "sign_dark"}),
    "Clinic": ("shop", "+Z", "CAFE", "wall_mortar", {"awning": "awning_brown"}),
    "Tenements": ("mansion", "+X", None, "wall_siding", {}),
    "Nightclub": ("club", "+X", "NIGHTCLUB", "wall_siding", {}),
    "RepairShop": ("shop", "+Z", "IZAKAYA", "wall_mortar", {"awning": "awning_red", "sign": "sign_dark"}),
    "PrintShop": ("shop", "+Z", "ARCADE", "wall_siding", {"awning": "awning_blue"}),
    "SouthHomes": ("apato", "+X", None, "wall_mortar", {"solid_balcony": True}),
    "StationHall": ("shop", "+Z", "STATION", "wall_siding", {"awning": "awning_blue", "sign": "sign_dark"}),
}
WALLS = ["wall_mortar", "wall_siding"]


def outer_kind(height):
    if height < 5:
        return "house1"
    return "apato" if height < 7 else "mansion"


def plots():
    text = SCENE.read_text(encoding="utf-8")
    pattern = r'\[node name="([^"]+)" type="Node3D" parent="\."[^\]]*\]\nscript = ExtResource\("[^"]+"\)\nbounds = AABB\(([^)]*)\)'
    for name, values in re.findall(pattern, text):
        x, y, z, sx, sy, sz = (float(v) for v in values.split(","))
        yield name, (x + sx / 2, z + sz / 2), (sx, sz), sy


def main():
    specs = []
    for seed, (name, (cx, cz), (sx, sz), height) in enumerate(plots()):
        if name in PLAN:
            kind, facing, door, wall, extra = PLAN[name]
        elif name.startswith("Outer"):
            kind, door, extra = outer_kind(height), None, {}
            facing = "+X" if cx < 0 else "-X"
            wall = WALLS[seed % 2]
        elif name.startswith("Skyline"):
            kind, facing, door, extra = "mansion", "+Z", None, {}
            wall = WALLS[seed % 2]
        else:
            continue
        rotation = {"+Z": 0, "-Z": 180, "+X": 90, "-X": -90}[facing]
        width, depth = (sx, sz) if facing in ("+Z", "-Z") else (sz, sx)
        door_a = 0.0
        if door:
            dx, dz = DOORS[door][0] - cx, DOORS[door][1] - cz
            door_a = {"+Z": dx, "-Z": -dx, "+X": -dz, "-X": dz}[facing]
        spec = {
            "name": "blk_" + name.lower().replace("-", "m"),
            "node": name,
            "kind": kind,
            "width": round(width, 3),
            "depth": round(depth, 3),
            "height": round(height, 3),
            "centre": [round(cx, 3), round(cz, 3)],
            "rotation_deg": rotation,
            "door_a": round(door_a, 3),
            "wall": wall,
            "seed": 1100 + seed,
        }
        spec.update(extra)
        specs.append(spec)
    OUT.write_text(json.dumps(specs, indent=1), encoding="utf-8")
    kinds = {}
    for s in specs:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"{len(specs)} buildings -> {OUT.name}: {kinds}")


if __name__ == "__main__":
    main()
