"""Author the Visual 0.11 parametric Japanese buildings as GLBs.

    blender -b --factory-startup --python client/tools/blender/jp_block.py -- <specs.json> <out_dir>

Every building is modelled in one canonical frame: the main facade faces
Blender -Y (Godot +Z), `width` runs along that facade and `depth` away from
it. Godot rotates each instance toward its real street (build_photoreal11.gd).
Kinds: apato (external corridor + steel stair), mansion (RC block), shop
(shopfront + flats above), house1 (single storey), school, club.
"""

import json
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import jp_houses as kit  # noqa: E402
from jp_houses import Face, ac_unit, carve, drip_mould, finial, gable_roof, pipe_run, window  # noqa: E402

kit.PALETTE.update({
    "roof_membrane": ((0.42, 0.43, 0.42), 0.9, 0.0),
    "concrete": ((0.60, 0.60, 0.58), 0.9, 0.0),
    "corridor_floor": ((0.36, 0.38, 0.37), 0.8, 0.0),
    "door_steel": ((0.72, 0.72, 0.68), 0.45, 0.3),
    "shutter": ((0.62, 0.63, 0.62), 0.5, 0.5),
    "awning_red": ((0.45, 0.10, 0.09), 0.8, 0.0),
    "awning_green": ((0.10, 0.28, 0.18), 0.8, 0.0),
    "awning_blue": ((0.10, 0.18, 0.36), 0.8, 0.0),
    "awning_brown": ((0.36, 0.24, 0.14), 0.8, 0.0),
    "sign_cream": ((0.86, 0.83, 0.74), 0.5, 0.0),
    "sign_dark": ((0.10, 0.11, 0.13), 0.5, 0.0),
    "neon": ((0.3, 0.7, 0.9), 0.3, 0.0),
    "neon_magenta": ((0.9, 0.2, 0.6), 0.3, 0.0),
    "neon_red": ((0.9, 0.1, 0.15), 0.3, 0.0),
    "neon_amber": ((0.9, 0.6, 0.2), 0.3, 0.0),
    "screen": ((0.05, 0.05, 0.06), 0.2, 0.0),
    "galvanized": ((0.62, 0.64, 0.64), 0.45, 0.8),
})
kit.TEXTURED.update({"concrete", "corridor_floor", "shutter"})

STAIR_W = 1.4
NEONS = ["neon", "neon_magenta", "neon_red", "neon_amber"]
NEON_LIGHT = {"neon": "LIGHT_cyan", "neon_magenta": "LIGHT_magenta", "neon_red": "LIGHT_red", "neon_amber": "LIGHT_amber"}


def axis_name(v):
    """Blender axis a vector points along, for sign markers read by Godot."""
    if abs(v.x) > 0.5:
        return "px" if v.x > 0 else "nx"
    return "py" if v.y > 0 else "ny"


def vertical_sign(b, f, a, z0, rnd, height=2.6, out=0.6):
    """Projecting vertical neon sign (sode kanban): dark box, neon frame, kanji by Godot."""
    neon = rnd.choice(NEONS)
    centre_out = out + 0.08
    for dz in (0.25, height - 0.25):
        f.box(b, a, z0 + dz, 0.06, 0.06, out + 0.1, (out + 0.1) / 2, "iron")
    f.box(b, a, z0 + height / 2, 0.14, height, 0.66, centre_out, "sign_dark")
    for side in (-1, 1):
        face = a + side * 0.075
        for dz in (0.06, height - 0.06):
            f.box(b, face, z0 + dz, 0.016, 0.03, 0.6, centre_out, neon)
        for dn in (-0.29, 0.29):
            f.box(b, face, z0 + height / 2, 0.016, height - 0.1, 0.03, centre_out + dn, neon)
        b.marker("SIGNV_" + axis_name(f.u * side) + "_" + neon, f.p(face + side * 0.012, z0 + height / 2, centre_out))
    b.marker(NEON_LIGHT[neon], f.p(a, z0 + height / 2, centre_out + 0.5))


def screen_billboard(b, top, W, D, rnd, y0=0.0):
    """Rooftop advertising screen facing the street, on an iron frame."""
    sw = min(4.5, W * 0.55)
    sh = sw * 0.5
    cx = rnd.uniform(-W / 2 + sw / 2 + 0.3, W / 2 - sw / 2 - 0.3)
    cy = y0 - D / 2 + 1.2
    for dx in (-sw / 2 + 0.2, sw / 2 - 0.2):
        b.box((cx + dx, cy + 0.25, top + 0.9 + sh / 2), (0.1, 0.1, 1.8 + sh), "iron")
        b.cylinder((cx + dx, cy + 0.25, top + 1.0), (cx + dx, cy + 1.3, top + 0.1), 0.04, "iron", segments=6)
    b.box((cx, cy, top + 1.8 + sh / 2), (sw + 0.16, 0.14, sh + 0.16), "iron")
    b.box((cx, cy - 0.075, top + 1.8 + sh / 2), (sw, 0.02, sh), "screen")
    b.marker(rnd.choice(["LIGHT_magenta", "LIGHT_cyan"]), (cx, cy - 1.2, top + 1.8 + sh / 2))


def battlements(b, W, D, top, height, cy=0.0, mat="stone"):
    """Crenellated parapet and corner pinnacles: the gothic roofline."""
    t = 0.22
    for s in (-1, 1):
        for length, fixed, along_x in ((W, cy + s * (D / 2 - t / 2), True), (D, s * (W / 2 - t / 2), False)):
            n = max(2, int(length / 0.95))
            for i in range(n):
                c = -length / 2 + (i + 0.5) * length / n
                pos = (c, fixed, top + height + 0.2) if along_x else (fixed, cy + c, top + height + 0.2)
                b.box(pos, (0.45, t + 0.04, 0.4) if along_x else (t + 0.04, 0.45, 0.4), mat)
    for sx in (-1, 1):
        for sy in (-1, 1):
            base = Vector((sx * (W / 2 - 0.25), cy + sy * (D / 2 - 0.25), top + height))
            b.box(base + Vector((0, 0, 0.3)), (0.5, 0.5, 0.6), mat)
            b.cylinder(base + Vector((0, 0, 0.6)), base + Vector((0, 0, 2.1)), 0.34, mat, segments=4, radius_end=0.0)
            finial(b, base + Vector((0, 0, 2.05)), 0.5)


def faces(W, D):
    return {
        "front": Face((0, -D / 2, 0), (1, 0, 0), (0, -1, 0)),
        "back": Face((0, D / 2, 0), (-1, 0, 0), (0, 1, 0)),
        "right": Face((W / 2, 0, 0), (0, 1, 0), (1, 0, 0)),
        "left": Face((-W / 2, 0, 0), (0, -1, 0), (-1, 0, 0)),
    }


def rotated_gable(b, W, D, eave, pitch, wall_mat, y0=0.0, **kw):
    """gable_roof() with its ridge turned to run along X (eaves front and back)."""
    first = len(b.parts)
    gable_roof(b, D, W, eave, pitch, wall_mat, **kw)
    turn = Matrix.Rotation(math.pi / 2, 4, "Z")
    shift = Matrix.Translation((0, y0, 0))
    for obj in b.parts[first:]:
        obj.data.transform(shift @ turn)


def parapet_roof(b, W, D, top, wall_mat, y0=0.0, height=0.75, tank=False, penthouse=False, seed=0, screen=None):
    rnd = random.Random(seed)
    cy = y0
    battlements(b, W, D, top, height, cy)
    if screen if screen is not None else rnd.random() < 0.35:
        screen_billboard(b, top, W, D, rnd, cy)
    b.box((0, cy, top + 0.08), (W - 0.1, D - 0.1, 0.16), "roof_membrane")
    t = 0.18
    for s in (-1, 1):
        b.box((0, cy + s * (D / 2 - t / 2), top + height / 2), (W, t, height), wall_mat)
        b.box((s * (W / 2 - t / 2), cy, top + height / 2), (t, D, height), wall_mat)
        b.box((0, cy + s * (D / 2 - t / 2), top + height + 0.02), (W + 0.04, t + 0.06, 0.04), "alu")
        b.box((s * (W / 2 - t / 2), cy, top + height + 0.02), (t + 0.06, D + 0.04, 0.04), "alu")
    # Roof drains, vent stacks and a couple of condensers.
    for s in (-1, 1):
        b.cylinder((s * (W / 2 - 0.5), cy + D / 2 - 0.5, top + 0.16), (s * (W / 2 - 0.5), cy + D / 2 - 0.5, top + 0.2), 0.08, "metal_paint")
    for k in range(rnd.randint(1, 3)):
        x = rnd.uniform(-W / 2 + 1.2, W / 2 - 1.2)
        y = cy + rnd.uniform(-D / 2 + 1.2, D / 2 - 1.2)
        ac_unit(b, (x, y, top + 0.45), (0, -1, 0))
    for k in range(2):
        x = rnd.uniform(-W / 2 + 0.6, W / 2 - 0.6)
        b.cylinder((x, cy + D / 2 - 0.9, top + 0.16), (x, cy + D / 2 - 0.9, top + 0.9), 0.05, "metal_paint", segments=8)
        b.cylinder((x, cy + D / 2 - 0.9, top + 0.9), (x, cy + D / 2 - 0.9, top + 0.98), 0.09, "metal_paint", segments=8)
    if penthouse:
        pw, pd, ph = min(3.0, W * 0.3), min(3.2, D * 0.45), 2.6
        px = W / 2 - pw / 2 - 0.6
        py = cy + D / 2 - pd / 2 - 0.6
        b.box((px, py, top + ph / 2), (pw, pd, ph), wall_mat)
        b.box((px, py, top + ph + 0.05), (pw + 0.1, pd + 0.1, 0.1), "alu")
        b.box((px - 0.3, py - pd / 2 - 0.02, top + 1.05), (0.85, 0.05, 1.95), "door_steel")
        b.box((px, py - pd / 2 - 0.35, top + 2.2), (1.2, 0.7, 0.07), "trim")
    if tank:
        tx = -W / 2 + 1.6
        ty = cy + D / 2 - 1.8
        for dx in (-0.6, 0.6):
            for dy in (-0.5, 0.5):
                b.box((tx + dx, ty + dy, top + 0.7), (0.08, 0.08, 1.4), "galvanized")
        b.box((tx, ty, top + 1.42), (1.4, 1.2, 0.06), "galvanized")
        b.box((tx, ty, top + 2.05), (1.5, 1.3, 1.2), "plastic_ivory")
        for k in range(4):
            b.box((tx, ty - 0.66, top + 1.6 + k * 0.3), (1.52, 0.02, 0.03), "trim")
        pipe_run(b, [(tx + 0.5, ty - 0.4, top + 1.5), (tx + 0.5, ty - 0.4, top + 0.25), (tx + 1.6, ty - 0.4, top + 0.25)], 0.03, "metal_paint", brackets=False)
    # TV aerial.
    ax = rnd.uniform(-W / 2 + 1, W / 2 - 1)
    ay = cy + D / 2 - 0.6
    b.cylinder((ax, ay, top + 0.16), (ax, ay, top + 2.0), 0.02, "alu", segments=8)
    b.cylinder((ax - 0.6, ay, top + 1.85), (ax + 0.6, ay, top + 1.85), 0.012, "alu", segments=6)
    for k in range(8):
        x = ax - 0.5 + k * 0.14
        b.cylinder((x, ay - 0.22, top + 1.85), (x, ay + 0.22, top + 1.85), 0.006, "alu", segments=5)


def railing(b, f, a0, a1, z, out, height=1.05, solid=None):
    """Aluminium balcony railing (or solid parapet) along a face between a0 and a1."""
    w = a1 - a0
    c = (a0 + a1) / 2
    if solid:
        f.box(b, c, z + height / 2, w, height, 0.12, out, solid)
        f.box(b, c, z + height + 0.02, w + 0.02, 0.04, 0.16, out, "alu")
        return
    f.box(b, c, z + height, w, 0.05, 0.06, out, "alu")
    f.box(b, c, z + 0.12, w, 0.035, 0.04, out, "alu")
    n = max(2, int(w / 0.11))
    for i in range(n + 1):
        f.box(b, a0 + 0.02 + i * (w - 0.04) / n, z + 0.55, 0.016, 0.9, 0.016, out, "alu")


def laundry(b, f, a0, a1, z, out, rnd):
    for a in (a0 + 0.12, a1 - 0.12):
        f.box(b, a, z + 1.65, 0.03, 0.03, 0.5, out - 0.2, "alu")
    b.cylinder(f.p(a0 + 0.1, z + 1.7, out - 0.05), f.p(a1 - 0.1, z + 1.7, out - 0.05), 0.016, "alu", segments=8)
    colours = ["glass_frosted", "plastic_ivory", "awning_blue", "sign_cream", "awning_red", "soffit"]
    a = a0 + 0.3
    while a < a1 - 0.4 and rnd.random() < 0.85:
        w = rnd.uniform(0.25, 0.55)
        h = rnd.uniform(0.35, 0.8)
        f.box(b, a + w / 2, z + 1.68 - h / 2, w, h, 0.01, out - 0.05, rnd.choice(colours))
        a += w + rnd.uniform(0.05, 0.25)


def steel_door(b, f, a, z, name_plate=True):
    f.cut(b, a, z + 1.0, 0.9, 2.02, depth=0.2)
    f.box(b, a, z + 0.99, 0.84, 1.96, 0.04, -0.07, "door_steel")
    f.box(b, a - 0.3, z + 1.0, 0.04, 0.16, 0.03, -0.04, "alu")
    f.box(b, a, z + 1.35, 0.3, 0.05, 0.01, -0.045, "dark")
    if name_plate:
        f.box(b, a + 0.62, z + 1.5, 0.16, 0.08, 0.02, 0.01, "plastic_ivory")
        f.box(b, a + 0.62, z + 1.3, 0.07, 0.1, 0.03, 0.015, "dark")


def stair_tower(b, x0, y_front, base, fh, floors, side=1):
    """Switchback steel stair beside the building; lands on the corridor at each floor."""
    run = 2.2
    half = fh / 2
    xs = (x0 + side * 0.35, x0 + side * 1.05)
    for i in range(floors - 1):
        z0 = base + i * fh
        for j, (ya, yb) in enumerate(((y_front + 0.25, y_front + 0.25 + run), (y_front + 0.25 + run, y_front + 0.25))):
            za = z0 + j * half
            steps = 8
            x = xs[j]
            for k in range(steps):
                t = (k + 0.5) / steps
                y = ya + (yb - ya) * t
                z = za + half * (k + 1) / steps
                b.box((x, y, z), (0.66, run / steps + 0.02, 0.035), "galvanized")
            for sx in (-0.34, 0.34):
                p0 = Vector((x + sx, ya, za))
                p1 = Vector((x + sx, yb, za + half))
                b.oriented((p0 + p1) / 2, p1 - p0, (1, 0, 0), ((p1 - p0).length, 0.03, 0.18), "metal_paint")
            outer = x + side * 0.36
            p0 = Vector((outer, ya, za + 0.95))
            p1 = Vector((outer, yb, za + half + 0.95))
            b.cylinder(p0, p1, 0.022, "metal_paint", segments=8)
            for k in range(4):
                q = Vector((outer, ya, za)).lerp(Vector((outer, yb, za + half)), k / 3)
                b.cylinder(q, q + Vector((0, 0, 0.95)), 0.015, "metal_paint", segments=6)
        # Mid landing at the back and floor landing at the front.
        b.box((x0 + side * STAIR_W / 2, y_front + 0.25 + run + 0.45, z0 + half), (STAIR_W, 0.9, 0.08), "galvanized")
        b.box((x0 + side * STAIR_W / 2, y_front + 0.6, z0 + fh), (STAIR_W, 1.2, 0.08), "galvanized")
    top = base + (floors - 1) * fh
    for dy in (0.05, 0.25 + run + 0.85):
        b.box((x0 + side * (STAIR_W - 0.05), y_front + dy, top / 2 + 0.5), (0.1, 0.1, top + 1.0), "metal_paint")


def build_apato(b, s, rnd):
    W, D = s["width"], s["depth"]
    base, fh = 0.3, 2.8
    floors = max(2, min(3, round((s["height"] - 1.2) / fh)))
    cd = 1.25  # corridor depth, kept inside the plot
    y0 = cd / 2  # centre of the enclosed block
    body_d = D - cd
    top = base + floors * fh
    wall_mat = s["wall"]
    b.box((0, y0, base / 2), (W - 0.04, body_d - 0.04, base), "foundation")
    wall = b.box((0, y0, (base + top) / 2), (W, body_d, top - base), wall_mat)
    f = faces(W, body_d)
    for key in f:
        f[key].o += Vector((0, y0, 0))
    front, back = f["front"], f["back"]
    units = max(2, int((W - 0.4) / 3.4))
    uw = W / units
    # Corridor slabs, fascia and solid balustrade on the upper floors.
    b.box((0, -D / 2 + cd / 2, 0.08), (W + STAIR_W, cd, 0.16), "porch_tile")
    for i in range(1, floors):
        z = base + i * fh
        b.box((0, -D / 2 + cd / 2, z - 0.09), (W, cd, 0.18), "concrete")
        b.box((0, -D / 2 + cd / 2, z + 0.005), (W - 0.1, cd - 0.1, 0.01), "corridor_floor")
        b.box((0, -D / 2 + 0.06, z + 0.5), (W, 0.12, 1.0), wall_mat)
        b.box((0, -D / 2 + 0.06, z + 1.02), (W + 0.02, 0.18, 0.05), "alu")
        b.box((0, -D / 2 + cd / 2, z - 0.19), (W - 0.1, cd - 0.1, 0.01), "soffit")
    for k in range(units + 1):
        x = -W / 2 + 0.08 + k * (W - 0.16) / units
        b.box((x, -D / 2 + 0.1, (base + (floors - 1) * fh) / 2), (0.12, 0.12, base + (floors - 1) * fh), "metal_paint")
    # Bare fluorescent tubes under each corridor ceiling.
    for i in range(floors):
        ceiling = base + (i + 1) * fh - 0.28
        for u in range(units):
            x = -W / 2 + (u + 0.5) * uw
            b.box((x, -D / 2 + cd * 0.6, ceiling), (0.7, 0.1, 0.05), "lamp")
            if u % 2 == 0:
                b.marker("LIGHT_fluo", (x, -D / 2 + cd * 0.6, ceiling - 0.3))
    for i in range(floors):
        z = base + i * fh
        for u in range(units):
            ua = -W / 2 + (u + 0.5) * uw
            steel_door(b, front, ua - uw * 0.22, z)
            window(b, front, ua + uw * 0.2, z + 1.1, 0.9, 0.85, grille=True, frosted=True)
            front.box(b, ua + uw * 0.2 + 0.72, z + 1.35, 0.3, 0.42, 0.14, 0.07, "plastic_ivory")
            # Back: sliding door to a balcony (or a small yard on the ground floor).
            window(b, back, -ua + 0.3, z + 0.12, 1.7, 1.85, dark=True)
            window(b, back, -ua - uw * 0.36, z + 1.0, 0.7, 0.8, frosted=True, shutter=True)
            if i > 0:
                a0, a1 = -ua - uw / 2 + 0.05, -ua + uw / 2 - 0.05
                back.box(b, -ua, z - 0.02, uw - 0.02, 0.14, 0.95, 0.47, "concrete")
                railing(b, back, a0, a1, z + 0.05, 0.9, solid=wall_mat if s.get("solid_balcony") else None)
                back.box(b, a1 + 0.03, z + 0.9, 0.03, 1.75, 0.9, 0.47, "glass_frosted")
                laundry(b, back, a0, a1, z, 0.8, rnd)
                if rnd.random() < 0.8:
                    ac_unit(b, back.p(a1 - 0.6, z + 0.35, 0.55), (0, 1, 0))
            elif rnd.random() < 0.7:
                ac_unit(b, back.p(-ua + uw * 0.3, 0.35, 0.45), (0, 1, 0))
    for side_face in (f["left"], f["right"]):
        for i in range(floors):
            window(b, side_face, 0.0, base + i * fh + 1.2, 0.6, 0.8, frosted=True)
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []
    stair_tower(b, W / 2, -D / 2, base, fh, floors, side=1)
    rotated_gable(b, W + 0.2, D, top, math.radians(28), wall_mat, ov_e=0.45, ov_g=0.35)
    return top


def build_mansion(b, s, rnd):
    W, D = s["width"], s["depth"]
    base, fh = 0.3, 2.9
    floors = max(3, min(5, round((s["height"] - 0.8) / fh)))
    top = base + floors * fh
    wall_mat = s["wall"]
    b.box((0, 0, base / 2), (W - 0.04, D - 0.04, base), "foundation")
    # 1 m corridor in front and 1 m balconies behind stay inside the plot.
    wall = b.box((0, 0, (base + top) / 2), (W, D - 2.0, top - base), wall_mat)
    f = faces(W, D - 2.0)
    front, back = f["front"], f["back"]
    bays = max(2, int(W / 3.2))
    bw = W / bays
    for i in range(floors):
        z = base + i * fh
        for k in range(bays):
            a = -W / 2 + (k + 0.5) * bw
            if i == 0 and abs(a - s.get("door_a", 0.0)) < bw / 2:
                front.cut(b, a, base + 1.25, 1.9, 2.5, depth=1.0)
                front.box(b, a, base + 1.2, 1.7, 2.3, 0.02, -0.45, "glass")
                for m in (-0.85, 0.0, 0.85):
                    front.box(b, a + m, base + 1.2, 0.05, 2.3, 0.06, -0.44, "alu")
                front.box(b, a, base + 2.75, 2.8, 0.12, 1.5, 0.5, "concrete")
                b.marker("LIGHT_warm", front.p(a, base + 2.4, 0.9))
                continue
            if i == 0:
                window(b, front, a, z + 1.0, 1.4, 1.1, grille=True)
            else:
                steel_door(b, front, a - bw * 0.2, z)
                window(b, front, a + bw * 0.22, z + 1.1, 0.8, 0.8, grille=True, frosted=True)
            window(b, back, -a, z + 0.12, 1.8, 1.9, dark=True)
        # Front corridor with solid parapet and back balconies with steel top rails.
        if i > 0:
            b.box((0, -D / 2 + 0.5, z - 0.08), (W, 1.0, 0.16), "concrete")
            b.box((0, -D / 2 + 0.07, z + 0.55), (W, 0.14, 1.1), wall_mat)
            b.box((0, -D / 2 + 0.07, z + 1.12), (W + 0.02, 0.2, 0.05), "alu")
        b.box((0, D / 2 - 0.5, z - 0.08 if i else 0.08), (W, 1.0, 0.16), "concrete")
        if i > 0:
            railing(b, back, -W / 2 + 0.05, W / 2 - 0.05, z, 0.95, height=1.1, solid="concrete")
        for k in range(bays):
            a = -W / 2 + (k + 0.5) * bw
            if i > 0:
                back.box(b, -a - bw / 2, z + 0.9, 0.03, 1.75, 0.95, 0.47, "glass_frosted")
                laundry(b, back, -a - bw / 2 + 0.1, -a + bw / 2 - 0.1, z, 0.8, rnd)
                if rnd.random() < 0.75:
                    ac_unit(b, back.p(-a + bw * 0.25, z + 0.35, 0.55), (0, 1, 0))
    for k in range(bays + 1):
        a = -W / 2 + k * bw
        front.box(b, max(-W / 2 + 0.12, min(W / 2 - 0.12, a)), (base + top) / 2, 0.24, top - base, 0.9, 0.45, wall_mat)
    for side_face in (f["left"], f["right"]):
        for i in range(floors):
            window(b, side_face, -0.6, base + i * fh + 1.0, 1.2, 1.1, shutter=True)
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []
    if rnd.random() < 0.5:
        vertical_sign(b, front, W / 2 - 0.5, base + fh * 1.1, rnd, height=min(3.4, fh * (floors - 1.3)), out=1.0)
    parapet_roof(b, W, D, top, wall_mat, tank=True, penthouse=floors >= 4, seed=s["seed"])
    return top


def build_shop(b, s, rnd, club=False, force_gable=False):
    W, D = s["width"], s["depth"]
    base, gh, fh = 0.15, 3.4, 2.8
    upper = max(0, min(2, round((s["height"] - gh - 0.9) / fh)))
    top = base + gh + upper * fh
    wall_mat = s["wall"]
    b.box((0, 0, base / 2), (W - 0.04, D - 0.04, base), "foundation")
    wall = b.box((0, 0, (base + top) / 2), (W, D, top - base), wall_mat)
    f = faces(W, D)
    front = f["front"]
    da = s.get("door_a", 0.0)
    shop_w = min(W - 0.8, max(3.2, W * 0.8))
    if club:
        # Windowless club front: steel door, neon strips and a dark panel facade.
        front.box(b, 0, base + gh / 2, W - 0.1, gh, 0.08, 0.05, "trim")
        front.cut(b, da, base + 1.15, 1.3, 2.3, depth=0.6)
        front.box(b, da, base + 1.1, 1.2, 2.2, 0.05, -0.26, "door_steel")
        for z, tube in ((base + 2.7, "neon_red"), (base + 0.35, "neon_magenta")):
            front.box(b, 0, z, W - 0.4, 0.05, 0.05, 0.12, tube)
        front.box(b, da, base + 2.55, 2.2, 0.1, 1.1, 0.55, "trim")
        drip_mould(b, front, da, base + 2.3, 1.3)
        b.marker("LIGHT_red", front.p(da, base + 2.2, 0.8))
        b.marker("LIGHT_magenta", front.p(-W / 4, 1.2, 0.6))
    else:
        front.cut(b, 0, base + 1.4, shop_w, 2.8, depth=1.0)
        rec = -0.45
        # Glazed shopfront with a door where the game's entrance is.
        front.box(b, 0, base + 0.2, shop_w, 0.4, 0.1, rec, "alu_dark")
        front.box(b, 0, base + 1.5, shop_w - 0.1, 2.2, 0.02, rec, "glass_lit")
        b.marker("LIGHT_window", front.p(0, base + 1.8, -1.4))
        front.box(b, 0, base + 2.72, shop_w, 0.16, 0.08, rec, "alu_dark")
        n = max(2, int(shop_w / 1.2))
        for k in range(n + 1):
            front.box(b, -shop_w / 2 + k * shop_w / n, base + 1.4, 0.06, 2.8, 0.1, rec, "alu_dark")
        front.box(b, da, base + 1.1, 0.95, 2.1, 0.03, rec + 0.03, "glass_lit")
        front.box(b, da, base + 1.1, 1.0, 0.04, 0.06, rec + 0.05, "alu")
        # Half-raised roller shutter box above the glazing.
        front.box(b, 0, base + 2.62, shop_w, 0.34, 0.3, -0.1, "shutter")
        # Awning over the pavement.
        aw = s.get("awning", "awning_red")
        slope = Matrix.Rotation(math.radians(22), 4, "X")  # outer edge lower
        c = front.p(0, base + 2.95, 0.55)
        b.box(c, (shop_w + 0.2, 1.1, 0.04), aw, rot=slope)
        b.box(front.p(0, base + 2.72, 1.06), (shop_w + 0.2, 0.03, 0.22), aw)
        for sx in (-1, 1):
            b.cylinder(front.p(sx * (shop_w / 2 + 0.05), base + 2.75, 1.05), front.p(sx * (shop_w / 2 + 0.05), base + 3.2, 0.05), 0.012, "alu_dark", segments=6)
    # Sign band where the shop name label is mounted by Godot.
    sign = "sign_dark" if club else s.get("sign", "sign_cream")
    # Raised clear of the awning so the name reads from the isometric camera.
    front.box(b, 0, base + gh + 0.2, W - 0.2, 0.62, 0.18, 0.1, sign)
    front.box(b, 0, base + gh + 0.55, W - 0.1, 0.05, 0.24, 0.12, "alu")
    band_neon = rnd.choice(NEONS)
    for dz in (-0.33, 0.33):
        front.box(b, 0, base + gh + 0.2 + dz, W - 0.26, 0.025, 0.025, 0.2, band_neon)
    b.marker(NEON_LIGHT[band_neon], front.p(0, base + gh + 0.2, 1.1))
    if not club:
        vertical_sign(b, front, -W / 2 + 0.45, base + 1.2, rnd, height=2.4 + (1.8 if upper else 0.0))
    for i in range(upper):
        z = base + gh + 0.35 + i * fh
        n = max(2, int(W / 2.8))
        for k in range(n):
            a = -W / 2 + (k + 0.5) * W / n
            window(b, front, a, z + 0.85, 1.3, 1.1, shutter=True, dark=club)
        for face_key in ("right", "left", "back"):
            window(b, f[face_key], 0.0, z + 1.0, 1.0, 1.0, frosted=face_key != "back", shutter=face_key == "back")
    for face_key in ("right", "left"):
        f[face_key].box(b, -D / 2 + 1.0, 1.4, 0.3, 0.4, 0.15, 0.08, "plastic_ivory")
    ac_unit(b, f["right"].p(D / 2 - 1.2, 0.35, 0.45), (1, 0, 0))
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []
    if force_gable or (upper >= 1 and not club and rnd.random() < 0.5):
        rotated_gable(b, W, D, top, math.radians(34), wall_mat, ov_e=0.4, ov_g=0.3)
    else:
        parapet_roof(b, W, D, top, wall_mat, seed=s["seed"])
    return top


def build_house1(b, s, rnd):
    W, D = s["width"], s["depth"]
    base, eave = 0.45, 3.1
    wall_mat = s["wall"]
    b.box((0, 0, base / 2), (W - 0.04, D - 0.04, base), "foundation")
    wall = b.box((0, 0, (base + eave) / 2), (W, D, eave - base), wall_mat)
    f = faces(W, D)
    front = f["front"]
    da = s.get("door_a", -W * 0.25)
    front.cut(b, da, base + 1.1, 1.2, 2.2, depth=1.2)
    front.box(b, da, base + 1.02, 0.86, 2.02, 0.05, -0.55, "door_wood")
    front.box(b, da, base + 2.35, 1.6, 0.08, 0.9, 0.45, "trim")
    front.box(b, da + 0.85, base + 1.9, 0.1, 0.2, 0.12, 0.08, "lamp")
    b.marker("LIGHT_warm", front.p(da + 0.85, base + 1.8, 0.4))
    b.box(front.p(da, base / 2, 0.2), (1.4, 1.4, base), "porch_tile")
    for a in (x for x in (-W / 2 + 1.3, W * 0.1, W / 2 - 1.3) if abs(x - da) > 1.4):
        window(b, front, a, base + 0.8, 1.65, 1.1, grille=True)
    for key in ("right", "left", "back"):
        window(b, f[key], 0.0, base + 1.0, 1.2, 0.9, grille=key != "back")
    f["right"].box(b, D * 0.2, 1.3, 0.48, 0.68, 0.24, 0.13, "plastic_ivory")
    ac_unit(b, f["right"].p(-D * 0.2, 0.35, 0.45), (1, 0, 0))
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []
    rotated_gable(b, W, D, eave, math.radians(36), wall_mat)
    return eave


def build_school(b, s, rnd):
    W, D = s["width"], s["depth"]
    base, fh = 0.3, 3.5
    floors = max(2, min(3, round((s["height"] - 0.8) / fh)))
    top = base + floors * fh
    wall_mat = s["wall"]
    b.box((0, 0, base / 2), (W - 0.04, D - 0.04, base), "foundation")
    wall = b.box((0, 0, (base + top) / 2), (W, D, top - base), wall_mat)
    f = faces(W, D)
    front = f["front"]
    da = s.get("door_a", 0.0)
    bays = max(3, int(W / 3.0))
    bw = W / bays
    for i in range(floors):
        z = base + i * fh
        for k in range(bays):
            a = -W / 2 + (k + 0.5) * bw
            if i == 0 and abs(a - da) < bw / 2:
                front.cut(b, da, base + 1.3, 2.4, 2.6, depth=1.2)
                front.box(b, da, base + 1.25, 2.2, 2.4, 0.02, -0.55, "glass")
                for m in (-1.1, -0.55, 0.0, 0.55, 1.1):
                    front.box(b, da + m, base + 1.25, 0.05, 2.4, 0.06, -0.54, "alu")
                continue
            window(b, front, a, z + 0.9, bw - 0.5, 1.7)
            window(b, f["back"], -a, z + 0.9, bw - 0.5, 1.7)
        # Continuous concrete sun ledge above each floor of windows.
        front.box(b, 0, z + fh - 0.35, W, 0.12, 0.7, 0.35, "concrete")
        f["back"].box(b, 0, z + fh - 0.35, W, 0.12, 0.7, 0.35, "concrete")
    for key in ("left", "right"):
        for i in range(floors):
            window(b, f[key], 0.0, base + i * fh + 0.9, 1.6, 1.6)
    front.box(b, da, base + 2.9, 4.0, 0.14, 2.0, 1.0, "concrete")
    for sx in (-1.8, 1.8):
        b.cylinder(front.p(da + sx, 0, 1.8), front.p(da + sx, base + 2.85, 1.8), 0.1, "concrete", segments=12)
    # Bell tower with a slate spire; the clock moves onto its face.
    tw = 3.0
    ty = -D / 2 + tw / 2 + 0.2
    t_top = top + 5.0
    b.box((da, ty, (top + t_top) / 2), (tw, tw, t_top - top), "stone")
    for fx, fy in ((0, -1), (1, 0), (-1, 0)):
        b.box((da + fx * (tw / 2 + 0.01), ty + fy * (tw / 2 + 0.01), t_top - 1.3), (0.5 if fy else 0.04, 0.04 if fy else 0.5, 1.6), "dark")
    b.marker("LIGHT_candle", (da, ty, t_top - 1.3))
    b.cylinder((da, ty, t_top), (da, ty, t_top + 4.2), tw * 0.78, "roof_slate", segments=4, radius_end=0.0)
    finial(b, (da, ty, t_top + 4.1), 1.4)
    clock = Vector((da, -D / 2 + 0.18, top + 2.6))
    b.cylinder(clock, clock + Vector((0, -0.06, 0)), 0.6, "plastic_ivory", segments=24)
    b.cylinder(clock + Vector((0, -0.06, 0)), clock + Vector((0, -0.075, 0)), 0.05, "dark", segments=8)
    b.marker("LIGHT_warm", front.p(da, base + 2.6, 1.6))
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []
    parapet_roof(b, W, D, top, wall_mat, height=1.0, seed=s["seed"])
    return top


def build_station(b, s, rnd):
    top = build_shop(b, s, rnd, force_gable=True)
    W, D = s["width"], s["depth"]
    front = faces(W, D)["front"]
    ridge = top + (D / 2) * math.tan(math.radians(34))
    finial(b, (0, 0, ridge + 0.2), 3.2)  # spire on the ridge centre
    for x in (-W / 2 + 0.3, W / 2 - 0.3):
        b.cylinder((x, -D / 2 - 0.3, 0), (x, -D / 2 - 0.3, top + 1.4), 0.2, "stone", segments=6)
        finial(b, (x, -D / 2 - 0.3, top + 1.35), 1.2)
    clock = front.p(0, top - 0.55, 0.14)
    b.cylinder(clock, clock + Vector((0, -0.06, 0)), 0.5, "plastic_ivory", segments=24)
    b.marker("LIGHT_amber", front.p(0, top - 0.4, 1.0))
    return top


BUILDERS = {
    "apato": build_apato,
    "mansion": build_mansion,
    "shop": build_shop,
    "club": lambda b, s, rnd: build_shop(b, s, rnd, club=True),
    "house1": build_house1,
    "school": build_school,
    "station": build_station,
}


def main():
    specs_path, out = sys.argv[sys.argv.index("--") + 1:][:2]
    specs = json.load(open(specs_path, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    only = os.environ.get("JP_BLOCK_ONLY")
    for s in specs:
        if only and s["name"] != only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        b = kit.Builder(s["name"])
        random.seed(s["seed"])
        top = BUILDERS[s["kind"]](b, s, random.Random(s["seed"]))
        print(f"BUILT {s['name']} kind={s['kind']} top={top:.2f}")
        kit.join_and_export(b, os.path.join(out, s["name"] + ".glb"))


if __name__ == "__main__":
    main()
