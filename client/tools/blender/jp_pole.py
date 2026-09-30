"""Author the Visual 0.11 Japanese concrete distribution pole (GLB).

    blender -b --factory-startup --python client/tools/blender/jp_pole.py -- <out_dir>

Blender +X becomes Godot +X (toward the street), Blender -Y becomes Godot +Z
(along the line). Wire attachment heights are mirrored in
res://tools/build_photoreal11.gd; keep both in sync.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import jp_houses as kit  # noqa: E402  shared builder, palette and export

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

kit.PALETTE.update({
    "pole_concrete": ((0.62, 0.62, 0.60), 0.85, 0.0),
    "galvanized": ((0.62, 0.64, 0.64), 0.45, 0.8),
    "porcelain": ((0.86, 0.86, 0.84), 0.2, 0.0),
    "transformer": ((0.58, 0.60, 0.60), 0.5, 0.4),
    "cable_black": ((0.03, 0.03, 0.03), 0.6, 0.0),
    "neon_red": ((0.9, 0.1, 0.15), 0.3, 0.0),
    "glass_lit": ((0.16, 0.10, 0.05), 0.3, 0.0),
    "iron": ((0.07, 0.07, 0.08), 0.35, 0.8),
})
kit.TEXTURED.add("pole_concrete")

SHAFT = 10.8
UPPER_ARM, LOWER_ARM, TELECOM = 10.15, 9.45, 6.2
WIRE_X = (-0.75, 0.0, 0.75)


def insulator(b, base):
    base = Vector(base)
    b.cylinder(base, base + Vector((0, 0, 0.12)), 0.018, "galvanized", segments=8)
    for k in range(3):
        z = 0.1 + k * 0.045
        b.cylinder(base + Vector((0, 0, z)), base + Vector((0, 0, z + 0.03)), 0.075 - k * 0.012, "porcelain", segments=14)


def crossarm(b, z, length=1.9):
    b.box((0, 0, z), (length, 0.08, 0.08), "galvanized")
    b.box((0, 0.045, z + 0.03), (length, 0.01, 0.02), "galvanized")
    for s in (-1, 1):  # diagonal braces back to the shaft
        b.cylinder((s * 0.55, 0, z - 0.02), (0, 0, z - 0.55), 0.018, "galvanized", segments=6)
    for x in WIRE_X:
        insulator(b, (x, 0, z + 0.04))


def build():
    b = kit.Builder("jp_pole")
    b.cylinder((0, 0, 0), (0, 0, SHAFT), 0.17, "pole_concrete", segments=18, radius_end=0.11)
    b.cylinder((0, 0, SHAFT), (0, 0, SHAFT + 0.05), 0.11, "galvanized", segments=18, radius_end=0.06)
    b.cylinder((0, 0, 0), (0, 0, 0.02), 0.26, "pole_concrete", segments=18)
    crossarm(b, UPPER_ARM)
    crossarm(b, LOWER_ARM, 1.7)
    # Pole-top transformer pair on a bracket facing the street.
    for y in (-0.28, 0.28):
        can = Vector((0.36, y, 7.9))
        b.cylinder(can - Vector((0, 0, 0.36)), can + Vector((0, 0, 0.36)), 0.22, "transformer", segments=20)
        b.cylinder(can + Vector((0, 0, 0.36)), can + Vector((0, 0, 0.4)), 0.2, "transformer", segments=20)
        for k in (-0.08, 0.08):
            insulator(b, can + Vector((k, 0, 0.36)))
        b.box(can + Vector((0.2, 0, 0.05)), (0.06, 0.18, 0.22), "transformer")
    b.box((0.2, 0, 7.45), (0.42, 0.9, 0.06), "galvanized")
    b.box((0.2, 0, 8.35), (0.42, 0.9, 0.06), "galvanized")
    for z in (7.45, 8.35):
        b.cylinder((0.0, -0.2, z), (0.0, 0.2, z), 0.19, "galvanized", segments=10)
    # Cut-out fuses and drop leads from the upper arm to the transformer.
    for x in (-0.45, 0.45):
        b.box((x, 0, 8.95), (0.06, 0.06, 0.34), "porcelain")
        b.cylinder((x, 0, 9.12), (x, 0, LOWER_ARM + 0.02), 0.006, "cable_black", segments=5)
        b.cylinder((x, 0, 8.78), (0.36, 0, 8.3), 0.006, "cable_black", segments=5)
    # Telecom clamp and cable junction box.
    b.box((-0.2, 0, TELECOM), (0.1, 0.24, 0.1), "galvanized")
    b.box((-0.3, 0.0, TELECOM - 0.55), (0.14, 0.32, 0.5), "transformer")
    # Step bolts spiralling from 2.3 m up to the transformer.
    for i in range(14):
        z = 2.3 + i * 0.42
        ang = i * math.pi / 2 + math.pi / 4
        r = 0.16 - (z / SHAFT) * 0.05
        d = Vector((math.cos(ang), math.sin(ang), 0))
        b.cylinder(d * r * 0.8 + Vector((0, 0, z)), d * (r + 0.2) + Vector((0, 0, z)), 0.011, "metal_paint", segments=6)
    # Neighbourhood street light on a short arm over the road.
    b.cylinder((0.1, 0, 5.1), (1.05, 0, 5.35), 0.03, "galvanized", segments=8)
    b.box((1.12, 0, 5.3), (0.42, 0.16, 0.1), "plastic_ivory")
    b.box((1.12, 0, 5.24), (0.36, 0.12, 0.02), "lamp")
    b.marker("LIGHT_sodium", (1.12, 0, 5.05))
    # Surveillance camera watching the street, with a red status LED.
    b.cylinder((0.12, 0, 4.3), (0.42, 0, 4.3), 0.025, "galvanized", segments=6)
    b.oriented((0.55, 0, 4.22), (1, 0, -0.35), (0, 1, 0), (0.3, 0.12, 0.12), "plastic_ivory")
    b.cylinder((0.7, 0, 4.17), (0.74, 0, 4.155), 0.04, "dark", segments=10)
    b.box((0.5, 0.065, 4.27), (0.02, 0.01, 0.02), "neon_red")
    # Pole number plate facing the street and a band clamp.
    b.box((0.155, 0, 2.0), (0.012, 0.13, 0.36), "plastic_ivory")
    b.box((0.162, 0, 2.08), (0.004, 0.1, 0.04), "cable_black")
    b.cylinder((0, 0, 1.64), (0, 0, 1.72), 0.172, "metal_paint", segments=18)
    return b


def build_lantern():
    """Visual 0.12 gothic street lantern: fluted iron post and an amber glass cage."""
    b = kit.Builder("gothic_lantern")
    b.cylinder((0, 0, 0), (0, 0, 0.12), 0.2, "iron", segments=8)
    b.cylinder((0, 0, 0.12), (0, 0, 0.5), 0.13, "iron", segments=8, radius_end=0.08)
    b.cylinder((0, 0, 0.5), (0, 0, 3.1), 0.055, "iron", segments=8, radius_end=0.04)
    for z in (0.9, 2.2):
        b.cylinder((0, 0, z), (0, 0, z + 0.06), 0.075, "iron", segments=8)
    for sx, sy in ((1, 0), (-1, 0)):
        b.cylinder((0, 0, 2.95), (sx * 0.28, sy * 0.28, 3.25), 0.018, "iron", segments=5)
    head = Vector((0, 0, 3.35))
    b.box(head - Vector((0, 0, 0.2)), (0.3, 0.3, 0.04), "iron")
    for dx in (-0.14, 0.14):
        for dy in (-0.14, 0.14):
            b.box(head + Vector((dx, dy, 0)), (0.025, 0.025, 0.4), "iron")
    b.box(head, (0.24, 0.24, 0.34), "glass_lit")
    b.cylinder(head + Vector((0, 0, 0.2)), head + Vector((0, 0, 0.5)), 0.24, "iron", segments=4, radius_end=0.0)
    kit.finial(b, head + Vector((0, 0, 0.48)), 0.35)
    b.marker("LIGHT_lantern", head)
    return b


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit.join_and_export(build(), os.path.join(OUT, "jp_pole.glb"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit.join_and_export(build_lantern(), os.path.join(OUT, "gothic_lantern.glb"))


main()
