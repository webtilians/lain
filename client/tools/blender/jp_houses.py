"""Author the Visual 0.11 Japanese houses in Blender and export them as GLB.

Run headless (Blender 5.2):
    blender -b --factory-startup --python client/tools/blender/jp_houses.py -- <out_dir>

Units are metres. Blender +X is the street facade and Blender -Y becomes
Godot +Z (the side the isometric camera sees). Materials carry stable names
only; Godot replaces them with the shared Poly Haven PBR materials, so no
textures are embedded. Every textured part receives world-space box UVs
(1 UV unit = 1 m) so the Godot materials can scale by real texture size.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()
Z = Vector((0, 0, 1))

PALETTE = {
    # name: (rgb, roughness, metallic) - fallbacks only, Godot overrides by name.
    "wall_mortar": ((0.72, 0.68, 0.60), 0.9, 0.0),
    "wall_siding": ((0.70, 0.70, 0.67), 0.85, 0.0),
    "foundation": ((0.52, 0.52, 0.50), 0.95, 0.0),
    "roof_slate": ((0.23, 0.24, 0.26), 0.8, 0.0),
    "trim": ((0.30, 0.29, 0.28), 0.6, 0.0),
    "soffit": ((0.80, 0.79, 0.75), 0.8, 0.0),
    "alu": ((0.74, 0.75, 0.76), 0.35, 0.9),
    "alu_dark": ((0.22, 0.20, 0.18), 0.4, 0.8),
    "glass": ((0.05, 0.06, 0.07), 0.05, 0.0),
    "glass_frosted": ((0.62, 0.66, 0.68), 0.45, 0.0),
    "metal_paint": ((0.28, 0.28, 0.27), 0.5, 0.3),
    "plastic_ivory": ((0.82, 0.80, 0.74), 0.5, 0.0),
    "door_wood": ((0.30, 0.22, 0.16), 0.6, 0.0),
    "porch_tile": ((0.55, 0.53, 0.50), 0.8, 0.0),
    "dark": ((0.03, 0.03, 0.03), 0.9, 0.0),
    "lamp": ((0.95, 0.90, 0.78), 0.3, 0.0),
    "rubber": ((0.08, 0.08, 0.08), 0.8, 0.0),
    "brass": ((0.55, 0.43, 0.22), 0.35, 1.0),
    "stone": ((0.45, 0.44, 0.42), 0.7, 0.0),
    "glass_lit": ((0.16, 0.10, 0.05), 0.3, 0.0),
    "glass_lit_red": ((0.14, 0.02, 0.03), 0.3, 0.0),
    "iron": ((0.07, 0.07, 0.08), 0.35, 0.8),
}
# Parts in these materials get box UVs; others are untextured in Godot.
TEXTURED = {"wall_mortar", "wall_siding", "foundation", "porch_tile", "door_wood", "stone"}


def material(name):
    found = bpy.data.materials.get(name)
    if found:
        return found
    rgb, rough, metal = PALETTE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return m


def box_uv(mesh, scale=1.0):
    """World-space box projection: each face uses the plane of its dominant normal."""
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv = mesh.uv_layers.active.data
    for poly in mesh.polygons:
        n = poly.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            if axis == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif axis == 1:
                u, v = -co.x * (1 if n.y > 0 else -1), co.z
            else:
                u, v = co.x, co.y
            uv[li].uv = (u * scale, v * scale)


def plane_uv(mesh, origin, u_axis, v_axis):
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv = mesh.uv_layers.active.data
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            d = mesh.vertices[mesh.loops[li].vertex_index].co - origin
            uv[li].uv = (d.dot(u_axis), d.dot(v_axis))


class Builder:
    def __init__(self, label):
        self.label = label
        self.parts = []
        self.cutters = []
        self.markers = []
        self.count = 0

    def marker(self, name, pos):
        """Empty exported with the GLB; Godot turns LIGHT_*/SIGNV_* into lights and signs."""
        obj = bpy.data.objects.new(name, None)
        obj.location = Vector(pos)
        obj.empty_display_size = 0.1
        bpy.context.scene.collection.objects.link(obj)
        self.markers.append(obj)
        return obj

    def _object(self, bm, mat_name, smooth=False, uv=None):
        self.count += 1
        mesh = bpy.data.meshes.new(f"{self.label}_{self.count}")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(material(mat_name))
        if smooth:
            for p in mesh.polygons:
                p.use_smooth = True
        if uv is not None:
            plane_uv(mesh, *uv)
        elif mat_name in TEXTURED:
            box_uv(mesh)
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        self.parts.append(obj)
        return obj

    def box(self, center, size, mat_name, rot=None, uv=None):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if rot is not None:
            bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
        return self._object(bm, mat_name, uv=uv)

    def oriented(self, center, x_axis, y_axis, size, mat_name):
        """Box whose local X/Y axes are given (Z completes a right-handed frame)."""
        x = Vector(x_axis).normalized()
        y = Vector(y_axis).normalized()
        z = x.cross(y)
        rot = Matrix((x, y, z)).transposed().to_4x4()
        return self.box(center, size, mat_name, rot=rot)

    def cylinder(self, p0, p1, radius, mat_name, segments=12, radius_end=None):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                              radius2=radius if radius_end is None else radius_end, depth=d.length)
        rot = Z.rotation_difference(d.normalized()).to_matrix().to_4x4()
        bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
        bmesh.ops.translate(bm, vec=(p0 + p1) / 2, verts=bm.verts)
        return self._object(bm, mat_name, smooth=True)

    def prism(self, verts_xz, y0, y1, mat_name):
        """Extrude an XZ polygon between two Y planes (gable ends)."""
        bm = bmesh.new()
        front = [bm.verts.new((x, y0, z)) for x, z in verts_xz]
        back = [bm.verts.new((x, y1, z)) for x, z in verts_xz]
        bm.faces.new(list(reversed(front)))
        bm.faces.new(back)
        n = len(verts_xz)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((front[i], front[j], back[j], back[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._object(bm, mat_name)

    def cutter(self, center, size, rot=None):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if rot is not None:
            bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
        mesh = bpy.data.meshes.new(f"cut_{len(self.cutters)}")
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(mesh.name, mesh)
        self.cutters.append(obj)
        return obj


def bake_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    obj.data = mesh


def carve(obj, cutters, bevel=0.012):
    coll = bpy.data.collections.new(obj.name + "_cutters")
    bpy.context.scene.collection.children.link(coll)
    for c in cutters:
        # Reveal faces created by the cut inherit the cutter material: use the wall's.
        c.data.materials.append(obj.data.materials[0])
        coll.objects.link(c)
    mod = obj.modifiers.new("openings", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    try:
        mod.solver = "EXACT"
    except TypeError:
        pass
    if bevel:
        bev = obj.modifiers.new("edges", "BEVEL")
        bev.width = bevel
        bev.segments = 2
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(40)
        bev.use_clamp_overlap = True
    bake_modifiers(obj)
    for c in cutters:
        bpy.data.objects.remove(c)
    bpy.data.collections.remove(coll)
    box_uv(obj.data)


class Face:
    """A wall plane: a = horizontal coordinate along the wall, out = offset along normal."""

    def __init__(self, origin, along, normal):
        self.o = Vector(origin)
        self.u = Vector(along).normalized()
        self.n = Vector(normal).normalized()

    def p(self, a, z, out=0.0):
        return self.o + self.u * a + Z * z + self.n * out

    def box(self, b, a, z, width, height, depth, out, mat_name):
        """Box centred at (a, z) with its centre `out` metres in front of the plane."""
        return b.oriented(self.p(a, z, out), self.u, self.n, (width, depth, height), mat_name)

    def cut(self, b, a, z, width, height, depth=0.44):
        x, y = self.u, self.n
        rot = Matrix((x, y, x.cross(y))).transposed().to_4x4()
        b.cutter(self.p(a, z, 0.0), (width, depth, height), rot=rot)


def window_glass(frosted):
    """Most windows are dark; some are lit amber, a few crimson behind curtains."""
    roll = random.random()
    if roll < 0.24:
        return "glass_lit"
    if roll < 0.36:
        return "glass_lit_red"
    return "glass_frosted" if frosted else "glass"


def drip_mould(b, f, a, top, w):
    """Pointed-arch hood moulding above a window, with a keystone."""
    rise = math.tan(math.radians(34))
    half = w / 2 + 0.1
    apex = f.p(a, top + 0.06 + half * rise, 0.05)
    for s in (-1, 1):
        start = f.p(a + s * half, top + 0.06, 0.05)
        along = apex - start
        b.oriented((start + apex) / 2, along, f.n, (along.length + 0.05, 0.08, 0.09), "stone")
    b.oriented(apex + Z * 0.02, f.u, f.n, (0.12, 0.1, 0.16), "stone")


def window(b, f, a, sill, w, h, grille=False, shutter=False, frosted=False, dark=False, gothic=True):
    """Aluminium sliding window recessed into a carved opening."""
    top = sill + h
    zc = sill + h / 2
    alu = "alu_dark" if dark else "alu"
    glass = window_glass(frosted)
    f.cut(b, a, zc, w, h)
    if glass != "glass" and glass != "glass_frosted" and random.random() < 0.35:
        b.marker("LIGHT_window" if glass == "glass_lit" else "LIGHT_red", f.p(a, zc, -0.6))
    if gothic and w >= 0.8 and not shutter:
        drip_mould(b, f, a, top, w)
    rec = -0.11
    t = 0.045
    # Outer frame.
    f.box(b, a, top - t / 2, w, t, 0.07, rec, alu)
    f.box(b, a, sill + t / 2, w, t, 0.07, rec, alu)
    for s in (-1, 1):
        f.box(b, a + s * (w / 2 - t / 2), zc, t, h, 0.07, rec, alu)
    # Two overlapping sashes.
    sw = w / 2 + 0.02
    for i, s in enumerate((-1, 1)):
        ca = a + s * (w / 4 - 0.01)
        depth = rec - 0.015 + i * 0.03
        f.box(b, ca, zc, sw - 0.02, h - 2 * t, 0.012, depth, glass)
        f.box(b, ca, top - t - 0.02, sw, 0.035, 0.03, depth, alu)
        f.box(b, ca, sill + t + 0.02, sw, 0.035, 0.03, depth, alu)
        f.box(b, ca + s * (sw / 2 - 0.018), zc, 0.036, h - 2 * t, 0.03, depth, alu)
        f.box(b, ca - s * (sw / 2 - 0.018), zc, 0.036, h - 2 * t, 0.034, depth, alu)
    # Sill that projects past the wall.
    f.box(b, a, sill - 0.02, w + 0.08, 0.03, 0.2, -0.02, alu)
    if grille:
        n = max(3, int(w / 0.11))
        for i in range(n + 1):
            ga = a - w / 2 + 0.03 + i * (w - 0.06) / n
            f.box(b, ga, zc, 0.018, h + 0.06, 0.018, 0.075, alu)
        for gz in (sill - 0.01, top + 0.03):
            f.box(b, a, gz, w + 0.04, 0.03, 0.05, 0.075, alu)
        for s in (-1, 1):
            f.box(b, a + s * (w / 2 + 0.02), zc, 0.03, h + 0.1, 0.1, 0.03, alu)
    if shutter:
        f.box(b, a, top + 0.16, w + 0.14, 0.3, 0.26, 0.1, alu)
        for s in (-1, 1):
            f.box(b, a + s * (w / 2 + 0.035), zc, 0.05, h, 0.06, 0.02, alu)


def ac_unit(b, center, facing, mat="plastic_ivory"):
    """Outdoor split-AC unit: casing, fan disc and grille bars."""
    c = Vector(center)
    fwd = Vector(facing).normalized()
    side = Z.cross(fwd).normalized()
    b.oriented(c, side, fwd, (0.8, 0.28, 0.55), mat)
    fan = c + fwd * 0.142 + side * -0.12
    b.cylinder(fan - fwd * 0.004, fan + fwd * 0.004, 0.19, "dark", segments=20)
    for k in range(-3, 4):
        b.oriented(fan + fwd * 0.012 + Z * (k * 0.05), side, fwd, (0.4, 0.008, 0.008), mat)
    b.oriented(c + side * 0.28 + fwd * 0.142, side, fwd, (0.18, 0.006, 0.4), "dark")
    for s in (-0.3, 0.3):
        b.oriented(c + side * s - Z * 0.3, side, fwd, (0.06, 0.3, 0.05), "rubber")


def pipe_run(b, points, radius, mat_name, brackets=True):
    for p0, p1 in zip(points, points[1:]):
        b.cylinder(p0, p1, radius, mat_name, segments=10)
        if brackets and abs(Vector(p1).z - Vector(p0).z) > 1.0:
            steps = int(abs(Vector(p1).z - Vector(p0).z) / 1.1)
            for k in range(1, steps + 1):
                q = Vector(p0).lerp(Vector(p1), k / (steps + 1))
                b.box(q, (radius * 3.2, radius * 3.2, 0.03), mat_name)


def gargoyle(b, pos, outward):
    """Crouched stone gargoyle on a roof corner, leaning out over the street."""
    pos = Vector(pos)
    out = Vector(outward).normalized()
    side = Z.cross(out).normalized()
    b.oriented(pos, out, side, (0.3, 0.18, 0.2), "stone")
    b.oriented(pos + out * 0.22 + Z * 0.06, out, side, (0.16, 0.12, 0.13), "stone")
    b.oriented(pos + out * 0.31 + Z * 0.08, out, side, (0.06, 0.05, 0.04), "stone")
    for s in (-1, 1):
        wing = pos + side * s * 0.14 + Z * 0.12 - out * 0.04
        b.oriented(wing, out * 0.6 + Z * 0.8, side, (0.22, 0.03, 0.16), "stone")


def iron_crest(b, p0, p1, height=0.26, spacing=0.28):
    """Spiked iron cresting along a ridge or parapet edge."""
    p0, p1 = Vector(p0), Vector(p1)
    length = (p1 - p0).length
    b.cylinder(p0, p1, 0.012, "iron", segments=6)
    n = max(2, int(length / spacing))
    for i in range(n + 1):
        q = p0.lerp(p1, i / n)
        b.cylinder(q, q + Z * height, 0.022, "iron", segments=5, radius_end=0.0)


def finial(b, base, height=1.1):
    base = Vector(base)
    b.box(base + Z * 0.07, (0.16, 0.16, 0.14), "iron")
    b.cylinder(base + Z * 0.14, base + Z * (height * 0.7), 0.06, "iron", segments=6, radius_end=0.02)
    b.cylinder(base + Z * (height * 0.7), base + Z * (height * 0.78), 0.05, "iron", segments=8)
    b.cylinder(base + Z * (height * 0.78), base + Z * height, 0.03, "iron", segments=5, radius_end=0.0)


def gable_roof(b, W, D, eave, pitch, wall_mat, ov_e=0.6, ov_g=0.45, aerial=True, gothic=True):
    """Gable roof with the ridge along Blender Y: slabs, stepped slate courses,
    fascia, soffit, gutters with downpipes, barge boards, ridge cap, aerial."""
    hx, hy = W / 2, D / 2
    t = 0.08
    run = hx + ov_e
    ridge_z = eave + hx * math.tan(pitch)
    slope_len = run / math.cos(pitch)
    length_y = D + 2 * ov_g
    # Gable triangles close the attic under the slabs.
    b.prism([(-hx, eave - 0.02), (hx, eave - 0.02), (0, ridge_z - 0.06)], -hy, hy, wall_mat)
    # Gable louvre on the camera side.
    gv = Vector((0, -hy - 0.03, eave + hx * math.tan(pitch) * 0.45))
    b.box(gv, (0.55, 0.06, 0.4), "trim")
    for k in range(4):
        b.box(gv + Vector((0, -0.035, -0.14 + k * 0.09)), (0.5, 0.02, 0.03), "metal_paint")
    for s in (-1, 1):
        down = Vector((s * math.cos(pitch), 0, -math.sin(pitch)))
        along_y = Vector((0, 1, 0))
        normal = down.cross(along_y) * (-1 if s > 0 else 1)
        if normal.z < 0:
            normal = -normal
        mid = Vector((0, 0, ridge_z)) + down * (slope_len / 2) + normal * (t / 2)
        b.oriented(mid, down, along_y, (slope_len, length_y, t), "trim")
        # Tile courses: overlapping slates stepped along the slope.
        course = 0.3
        n = int(slope_len / course)
        top = Vector((0, 0, ridge_z)) + normal * t
        for i in range(n):
            start = top + down * (i * course + 0.05)
            # Each course sits slightly flatter than the slope so its lower edge steps up.
            tilt = Matrix.Rotation(math.radians(-3.5) * s, 3, along_y)
            d2 = (tilt @ down).normalized()
            n2 = (tilt @ normal).normalized()
            centre = start + d2 * (course * 0.55) + n2 * 0.018
            obj = b.oriented(centre, d2, along_y, (course * 1.12, length_y, 0.022), "roof_slate")
            # Continuous UVs measured from the ridge so courses do not repeat one strip.
            plane_uv(obj.data, top + Vector((0, -length_y / 2, 0)), d2, along_y)
        # Fascia board with gutter and soffit under the eave.
        eave_pt = Vector((0, 0, ridge_z)) + down * slope_len
        b.box(eave_pt + Vector((s * 0.02, 0, -0.06)), (0.035, length_y + 0.02, 0.22), "trim")
        b.box(Vector((s * (hx + ov_e / 2), 0, eave - ov_e * math.tan(pitch) - 0.01)), (ov_e, D + 2 * ov_g - 0.1, 0.02), "soffit")
        gutter_x = eave_pt.x + s * 0.09
        b.cylinder((gutter_x, -length_y / 2, eave_pt.z - 0.1), (gutter_x, length_y / 2, eave_pt.z - 0.1), 0.065, "metal_paint", segments=14)
        for gy in (-length_y / 2 + 0.3, length_y / 2 - 0.3):
            px = s * (hx + 0.08)
            pipe_run(b, [(gutter_x, gy, eave_pt.z - 0.12), (px, gy, eave_pt.z - 0.45), (px, gy, 0.15), (px + s * 0.18, gy, 0.05)], 0.04, "metal_paint")
    # Barge boards along both gables and a ridge cap.
    for gy in (-length_y / 2, length_y / 2):
        for s in (-1, 1):
            down = Vector((s * math.cos(pitch), 0, -math.sin(pitch)))
            up_n = Vector((s * math.sin(pitch), 0, math.cos(pitch)))
            mid = Vector((0, gy, ridge_z)) + down * (slope_len / 2) + up_n * 0.02
            b.oriented(mid, down, (0, 1, 0), (slope_len, 0.035, 0.24), "trim")
    b.box((0, 0, ridge_z + t + 0.06), (0.26, length_y + 0.06, 0.1), "roof_slate", uv=(Vector((0, -length_y / 2, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))))
    b.box((0, 0, ridge_z + t + 0.12), (0.12, length_y + 0.06, 0.05), "roof_slate", uv=(Vector((0, -length_y / 2, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))))
    if gothic:
        crest_z = ridge_z + t + 0.15
        iron_crest(b, (0, -length_y / 2 + 0.35, crest_z), (0, length_y / 2 - 0.35, crest_z))
        for gy in (-length_y / 2, length_y / 2):
            finial(b, (0, gy, crest_z - 0.03), 1.2)
        corner_z = eave - ov_e * math.tan(pitch) - 0.05
        for sx in (-1, 1):
            for sy in (-1, 1):
                gargoyle(b, (sx * (hx + ov_e * 0.55), sy * (length_y / 2 - 0.15), corner_z), (sx, 0, 0))
    if not aerial:
        return
    # TV aerial on the ridge, a very common 80s-90s silhouette.
    ay = -hy * 0.4
    mast_top = ridge_z + 1.6
    b.cylinder((0, ay, ridge_z), (0, ay, mast_top), 0.02, "alu", segments=8)
    b.cylinder((-0.7, ay, mast_top - 0.1), (0.7, ay, mast_top - 0.1), 0.012, "alu", segments=6)
    for k in range(9):
        x = -0.6 + k * 0.15
        b.cylinder((x, ay - 0.25, mast_top - 0.1), (x, ay + 0.25, mast_top - 0.1), 0.006, "alu", segments=5)


def build_house(spec):
    random.seed(spec["seed"])
    b = Builder(spec["name"])
    W, D = spec["width"], spec["depth"]
    hx, hy = W / 2, D / 2
    base = 0.45
    floor2 = 3.05
    eave = spec["eave"]
    pitch = math.radians(spec["pitch"])
    ov_e, ov_g = 0.6, 0.45
    wall_mat = spec["wall"]

    # Foundation, drip edge and walls.
    found = b.box((0, 0, base / 2), (W - 0.04, D - 0.04, base), "foundation")
    vents = []
    b.box((0, 0, base + 0.012), (W + 0.05, D + 0.05, 0.025), "alu_dark")
    wall = b.box((0, 0, (base + eave) / 2 + 0.012), (W, D, eave - base - 0.024), wall_mat)
    # Floor band between storeys.
    b.box((0, 0, floor2), (W + 0.05, D + 0.05, 0.16), "trim")

    front = Face((hx, 0, 0), (0, -1, 0), (1, 0, 0))   # street, Godot +X
    side = Face((0, -hy, 0), (1, 0, 0), (0, -1, 0))   # camera side, Godot +Z
    far = Face((0, hy, 0), (-1, 0, 0), (0, 1, 0))
    back = Face((-hx, 0, 0), (0, 1, 0), (-1, 0, 0))

    # Foundation ventilation grilles (carved into the foundation block).
    fcut = Builder(spec["name"] + "_fv")
    for f, spots in ((front, (-2.4, 2.4)), (side, (-1.8, 1.4)), (far, (0.0,)), (back, (-1.5, 1.5))):
        for a in spots:
            f.cut(fcut, a, 0.24, 0.36, 0.12, depth=0.1)
            f.box(b, a, 0.24, 0.34, 0.1, 0.01, -0.035, "metal_paint")
    carve(found, fcut.cutters, bevel=0.008)

    # --- Street facade ---------------------------------------------------
    door_w, door_h, porch = 1.25, 2.3, 0.85
    front.cut(b, spec["door_a"], base + door_h / 2 - 0.01, door_w, door_h + 0.02, depth=porch * 2)
    da = spec["door_a"]
    # Door leaf with vertical glass slit and lever handle.
    front.box(b, da + 0.12, base + 1.02, 0.88, 2.04, 0.05, -porch + 0.02, "door_wood")
    front.box(b, da + 0.35, base + 1.1, 0.12, 1.5, 0.012, -porch + 0.05, "glass_frosted")
    front.box(b, da - 0.24, base + 1.0, 0.03, 0.2, 0.04, -porch + 0.07, "alu")
    front.box(b, da - 0.43, base + 1.02, 0.34, 2.04, 0.012, -porch + 0.04, "glass_frosted")
    front.box(b, da, base + door_h - 0.12, door_w, 0.24, 0.05, -porch + 0.02, "soffit")
    # Porch floor, step and canopy.
    b.box(front.p(da, base / 2, -porch / 2 + 0.3), (porch + 0.6, door_w + 0.3, base), "porch_tile")
    b.box(front.p(da, 0.1, 0.72), (0.34, door_w + 0.5, 0.2), "porch_tile")
    front.box(b, da, base + door_h + 0.2, 1.7, 0.08, 0.95, 0.47, "trim")
    front.box(b, da, base + door_h + 0.15, 1.7, 0.02, 0.9, 0.47, "soffit")
    for s in (-1, 1):
        front.box(b, da + s * 0.78, base + door_h + 0.05, 0.03, 0.18, 0.7, 0.35, "alu_dark")
    # Entrance light, nameplate, intercom and letterbox.
    lamp = front.p(da + door_w / 2 + 0.18, base + 1.95, 0.08)
    b.box(lamp, (0.1, 0.12, 0.2), "alu_dark")
    b.box(lamp + Vector((0.04, 0, -0.02)), (0.04, 0.09, 0.14), "lamp")
    b.marker("LIGHT_warm", lamp + Vector((0.3, 0, -0.1)))
    front.box(b, da + door_w / 2 + 0.18, base + 1.45, 0.24, 0.1, 0.02, 0.01, "stone")
    front.box(b, da + door_w / 2 + 0.18, base + 1.2, 0.08, 0.13, 0.03, 0.015, "dark")
    front.box(b, da + door_w / 2 + 0.22, base + 0.85, 0.3, 0.36, 0.12, 0.06, "alu_dark")

    for a in spec["front_low"]:
        window(b, front, a, base + 0.85, 1.65, 1.1, grille=spec["grilles"])
    if spec["balcony"]:
        ba0, ba1 = spec["balcony"]
        bw = ba1 - ba0
        bc = (ba0 + ba1) / 2
        window(b, front, bc - 0.5, floor2 + 0.1, 1.7, 1.85, dark=True)
        # Cantilevered slab with drip, aluminium railing and laundry poles.
        front.box(b, bc, floor2 + 0.02, bw, 0.14, 0.95, 0.47, "trim")
        front.box(b, bc, floor2 - 0.07, bw - 0.04, 0.02, 0.9, 0.46, "soffit")
        rail_out = 0.9
        front.box(b, bc, floor2 + 1.05, bw, 0.06, 0.07, rail_out, "alu")
        front.box(b, bc, floor2 + 0.16, bw, 0.04, 0.05, rail_out, "alu")
        n = int(bw / 0.11)
        for i in range(n + 1):
            front.box(b, ba0 + 0.02 + i * (bw - 0.04) / n, floor2 + 0.6, 0.016, 0.88, 0.016, rail_out, "alu")
        for s in (ba0, ba1):
            b.box(front.p(s, floor2 + 0.6, 0.47), (0.9, 0.05, 1.0), "alu")
        for side_a in (ba0 + 0.15, ba1 - 0.15):
            front.box(b, side_a, floor2 + 1.55, 0.03, 0.03, 0.55, 0.3, "alu")
        for h in (floor2 + 1.62,):
            b.cylinder(front.p(ba0 + 0.1, h, 0.52), front.p(ba1 - 0.1, h, 0.52), 0.017, "alu", segments=8)
        ac_unit(b, front.p(bc + 0.95, floor2 + 0.4, 0.58), (1, 0, 0))
        others = [a for a in spec["front_high"] if not (ba0 - 0.5 < a < ba1 + 0.5)]
    else:
        others = spec["front_high"]
    for a in others:
        window(b, front, a, floor2 + 0.75, 1.65, 1.1, shutter=True)
    if spec.get("front_small"):
        window(b, front, spec["front_small"], floor2 + 1.0, 0.75, 0.9, frosted=True)

    # --- Camera side ------------------------------------------------------
    window(b, side, 1.3, base + 1.05, 1.2, 0.9, grille=True)
    window(b, side, -1.9, base + 1.45, 0.7, 0.5, frosted=True, grille=True)
    window(b, side, 0.9, floor2 + 0.75, 1.2, 1.1, shutter=True)
    window(b, side, -1.8, floor2 + 0.9, 0.6, 0.9, frosted=True)
    # Water heater, gas meter, electricity meter and AC with duct cover.
    side.box(b, -0.6, 1.35, 0.48, 0.68, 0.24, 0.13, "plastic_ivory")
    side.box(b, -0.6, 1.35, 0.3, 0.06, 0.012, 0.255, "dark")
    pipe_run(b, [side.p(-0.72, 1.0, 0.1), side.p(-0.72, 0.2, 0.1), side.p(-0.72, 0.2, 0.3)], 0.016, "metal_paint", brackets=False)
    side.box(b, 0.1, 1.05, 0.32, 0.4, 0.2, 0.1, "metal_paint")
    side.box(b, 0.1, 1.12, 0.12, 0.08, 0.012, 0.205, "glass")
    side.box(b, hx - 0.45, 1.75, 0.28, 0.38, 0.14, 0.07, "plastic_ivory")
    b.cylinder(side.p(hx - 0.45, 1.8, 0.14), side.p(hx - 0.45, 1.8, 0.2), 0.07, "glass_frosted", segments=16)
    ac_unit(b, side.p(2.3, 0.35, 0.45), (0, -1, 0))
    duct = [side.p(2.0, 0.5, 0.05), side.p(2.0, floor2 + 0.45, 0.05), side.p(1.55, floor2 + 0.45, 0.05)]
    for p0, p1 in zip(duct, duct[1:]):
        mid = (p0 + p1) / 2
        length = (p1 - p0).length
        vertical = abs((p1 - p0).z) > 0.1
        b.box(mid, (0.085, 0.07, length + 0.08) if vertical else (length + 0.08, 0.07, 0.085), "plastic_ivory")
    # --- Far and back walls (seen through gaps and from the corner) -------
    window(b, far, 0.8, base + 1.05, 1.2, 0.9)
    window(b, far, -1.2, floor2 + 0.8, 1.2, 1.0, shutter=True)
    window(b, back, -1.4, base + 0.95, 1.65, 1.1, grille=True)
    window(b, back, 1.6, base + 1.4, 0.7, 0.5, frosted=True)
    window(b, back, 0.0, floor2 + 0.75, 1.65, 1.1, shutter=True)
    carve(wall, b.cutters, bevel=0.015)
    b.cutters = []

    gable_roof(b, W, D, eave, pitch, wall_mat, ov_e, ov_g)
    return b


def join_and_export(b, path):
    parts = b.parts
    for o in parts:
        o.select_set(True)
    with bpy.context.temp_override(active_object=parts[0], object=parts[0],
                                   selected_objects=parts, selected_editable_objects=parts):
        bpy.ops.object.join()
    house = parts[0]
    house.name = b.label
    house.data.name = b.label
    with bpy.context.temp_override(active_object=house, object=house, selected_objects=[house]):
        bpy.ops.object.select_all(action="DESELECT")
    house.select_set(True)
    for m in b.markers:
        m.parent = house
        m.select_set(True)
    bpy.context.view_layer.objects.active = house
    kwargs = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                  export_yup=True, export_materials="EXPORT", export_tangents=True,
                  export_image_format="NONE")
    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError:
        kwargs.pop("export_image_format")
        bpy.ops.export_scene.gltf(**kwargs)
    tris = sum(len(p.vertices) - 2 for p in house.data.polygons)
    print(f"EXPORTED {path} tris={tris} markers={len(b.markers)} materials={len(house.data.materials)}")


HOUSES = [
    dict(name="jp_house_a", seed=11, width=6.8, depth=6.3, eave=5.6, pitch=38, wall="wall_mortar",
         grilles=True, balcony=None, door_a=0.0, front_low=(-2.05, 2.05),
         front_high=(-1.9, 1.9), front_small=0.0),
    dict(name="jp_house_b", seed=23, width=6.8, depth=6.3, eave=5.4, pitch=35, wall="wall_siding",
         grilles=False, balcony=(-3.0, 0.9), door_a=2.2, front_low=(-2.2, 0.1),
         front_high=(-1.9, 2.0), front_small=None),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for spec in HOUSES:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        join_and_export(build_house(spec), os.path.join(OUT, spec["name"] + ".glb"))


if __name__ == "__main__":
    main()
