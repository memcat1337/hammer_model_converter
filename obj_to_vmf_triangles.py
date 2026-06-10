import argparse
import math
import os
from typing import Dict, List, Tuple, Optional, Set

Vec3 = Tuple[float, float, float]
Edge = Tuple[int, int]

def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)

def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )

def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))

def norm(a: Vec3) -> Optional[Vec3]:
    l = length(a)
    if l < 0.000001:
        return None
    return (a[0] / l, a[1] / l, a[2] / l)

def center(vs: List[Vec3]) -> Vec3:
    if not vs:
        return (0.0, 0.0, 0.0)
    n = len(vs)
    return (
        sum(v[0] for v in vs) / n,
        sum(v[1] for v in vs) / n,
        sum(v[2] for v in vs) / n,
    )

def snap_value(v: float, grid: float) -> float:
    if grid <= 0:
        return v
    return round(v / grid) * grid

def snap_vec(v: Vec3, grid: float) -> Vec3:
    return (
        snap_value(v[0], grid),
        snap_value(v[1], grid),
        snap_value(v[2], grid),
    )

def blender_to_source(v: Vec3, scale: float, axis: str) -> Vec3:
    x, y, z = v
    if axis == "xzy":
        return (x * scale, -z * scale, y * scale)
    if axis == "xyz":
        return (x * scale, y * scale, z * scale)
    if axis == "source2":
        return (x * scale, y * scale, z * scale)
    if axis == "unreal":
        return (x * scale, -y * scale, z * scale)
    return (x * scale, -z * scale, y * scale)

def vec_key(v: Vec3, precision: int = 4) -> Tuple[float, float, float]:
    return (round(v[0], precision), round(v[1], precision), round(v[2], precision))

def get_vertex_id(v: Vec3, verts: List[Vec3], lookup: Dict[Tuple[float, float, float], int]) -> int:
    k = vec_key(v)
    if k in lookup:
        return lookup[k]
    idx = len(verts)
    verts.append(v)
    lookup[k] = idx
    return idx

def parse_obj(path: str, scale: float, grid: float, axis: str):
    raw_verts: List[Vec3] = []
    verts: List[Vec3] = []
    lookup: Dict[Tuple[float, float, float], int] = {}
    faces: List[List[int]] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("v "):
                p = line.split()
                if len(p) >= 4:
                    v = (float(p[1]), float(p[2]), float(p[3]))
                    v = blender_to_source(v, scale, axis)
                    v = snap_vec(v, grid)
                    raw_verts.append(v)
                continue

            if line.startswith("f "):
                ids: List[int] = []
                for token in line.split()[1:]:
                    a = token.split("/")[0]
                    if not a:
                        continue
                    i = int(a)
                    if i < 0:
                        i = len(raw_verts) + i + 1
                    i -= 1
                    if 0 <= i < len(raw_verts):
                        ids.append(get_vertex_id(raw_verts[i], verts, lookup))

                clean: List[int] = []
                for i in ids:
                    if not clean or clean[-1] != i:
                        clean.append(i)
                if len(clean) >= 2 and clean[0] == clean[-1]:
                    clean.pop()

                if len(set(clean)) >= 3:
                    faces.append(clean)

    return verts, faces

def face_points(face: List[int], verts: List[Vec3]) -> List[Vec3]:
    return [verts[i] for i in face]

def face_normal_ids(face: List[int], verts: List[Vec3]) -> Optional[Vec3]:
    pts = face_points(face, verts)
    if len(pts) < 3:
        return None

    c = center(pts)
    n = (0.0, 0.0, 0.0)

    for i in range(len(pts)):
        a = sub(pts[i], c)
        b = sub(pts[(i + 1) % len(pts)], c)
        n = add(n, cross(a, b))

    return norm(n)

def face_area_ids(face: List[int], verts: List[Vec3]) -> float:
    pts = face_points(face, verts)
    if len(pts) < 3:
        return 0.0

    c = center(pts)
    area = 0.0

    for i in range(len(pts)):
        area += length(cross(sub(pts[i], c), sub(pts[(i + 1) % len(pts)], c))) * 0.5

    return area

def triangulate(face: List[int], verts: List[Vec3], min_area: float) -> List[List[int]]:
    if len(face) <= 4:
        return [face] if face_area_ids(face, verts) >= min_area else []

    out: List[List[int]] = []
    for i in range(1, len(face) - 1):
        t = [face[0], face[i], face[i + 1]]
        if face_area_ids(t, verts) >= min_area:
            out.append(t)
    return out

def edge_key(a: int, b: int) -> Edge:
    return (a, b) if a < b else (b, a)

def build_basis(n: Vec3) -> Tuple[Vec3, Vec3]:
    candidates = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    base = min(candidates, key=lambda a: abs(dot(a, n)))
    u = norm(cross(base, n)) or (1.0, 0.0, 0.0)
    v = norm(cross(n, u)) or (0.0, 1.0, 0.0)
    return u, v

def order_polygon(ids: List[int], verts: List[Vec3], n: Vec3) -> List[int]:
    pts = face_points(ids, verts)
    c = center(pts)
    u, v = build_basis(n)

    def angle(i: int) -> float:
        p = sub(verts[i], c)
        return math.atan2(dot(p, v), dot(p, u))

    ordered = sorted(ids, key=angle)
    pts_ordered = face_points(ordered, verts)
    n2 = face_normal_from_points(pts_ordered)

    if n2 is not None and dot(n2, n) < 0:
        ordered.reverse()

    return ordered

def face_normal_from_points(pts: List[Vec3]) -> Optional[Vec3]:
    if len(pts) < 3:
        return None

    c = center(pts)
    n = (0.0, 0.0, 0.0)

    for i in range(len(pts)):
        a = sub(pts[i], c)
        b = sub(pts[(i + 1) % len(pts)], c)
        n = add(n, cross(a, b))

    return norm(n)

def is_convex_quad(q: List[int], verts: List[Vec3], n: Vec3, eps: float) -> bool:
    if len(q) != 4 or len(set(q)) != 4:
        return False

    signs = []
    for i in range(4):
        a = verts[q[i]]
        b = verts[q[(i + 1) % 4]]
        c = verts[q[(i + 2) % 4]]
        z = dot(cross(sub(b, a), sub(c, b)), n)
        if abs(z) <= eps:
            return False
        signs.append(z > 0)

    return all(s == signs[0] for s in signs)

def is_rect_like_quad(q: List[int], verts: List[Vec3], n: Vec3, rect_tolerance_deg: float) -> bool:
    if len(q) != 4:
        return False

    max_dev = math.sin(math.radians(rect_tolerance_deg))

    for i in range(4):
        a = verts[q[(i - 1) % 4]]
        b = verts[q[i]]
        c = verts[q[(i + 1) % 4]]
        e1 = norm(sub(a, b))
        e2 = norm(sub(c, b))
        if e1 is None or e2 is None:
            return False
        if abs(dot(e1, e2)) > max_dev:
            return False

    return True

def merge_triangles_to_quads(faces: List[List[int]], verts: List[Vec3], normal_tolerance_deg: float, rect_only: bool, rect_tolerance_deg: float) -> List[List[int]]:
    tris: List[List[int]] = []
    other: List[List[int]] = []

    for f in faces:
        if len(f) == 3:
            tris.append(f)
        else:
            other.append(f)

    edge_map: Dict[Edge, List[int]] = {}
    for ti, t in enumerate(tris):
        for i in range(3):
            e = edge_key(t[i], t[(i + 1) % 3])
            edge_map.setdefault(e, []).append(ti)

    used: Set[int] = set()
    merged: List[List[int]] = []
    cos_tol = math.cos(math.radians(normal_tolerance_deg))

    for ti, t in enumerate(tris):
        if ti in used:
            continue

        n1 = face_normal_ids(t, verts)
        if n1 is None:
            continue

        best = None

        for i in range(3):
            e = edge_key(t[i], t[(i + 1) % 3])
            candidates = edge_map.get(e, [])

            for tj in candidates:
                if tj == ti or tj in used:
                    continue

                t2 = tris[tj]
                n2 = face_normal_ids(t2, verts)
                if n2 is None:
                    continue

                if dot(n1, n2) < cos_tol:
                    continue

                all_ids = list(dict.fromkeys(t + t2))
                if len(all_ids) != 4:
                    continue

                avg_n = norm(add(n1, n2))
                if avg_n is None:
                    continue

                q = order_polygon(all_ids, verts, avg_n)

                if not is_convex_quad(q, verts, avg_n, eps=0.00001):
                    continue

                if rect_only and not is_rect_like_quad(q, verts, avg_n, rect_tolerance_deg):
                    continue

                best = (tj, q)
                break

            if best is not None:
                break

        if best is not None:
            tj, q = best
            used.add(ti)
            used.add(tj)
            merged.append(q)
        else:
            used.add(ti)
            merged.append(t)

    return other + merged

def choose_texture_axes(n: Vec3) -> Tuple[Vec3, Vec3]:
    return build_basis(n)

def fmt(v: Vec3) -> str:
    return f"{v[0]:.3f} {v[1]:.3f} {v[2]:.3f}"

def plane_points(face: List[Vec3], solid_center: Vec3) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    a = face[0]
    for i in range(1, len(face) - 1):
        b = face[i]
        c = face[i + 1]
        n = cross(sub(b, a), sub(c, a))
        if length(n) < 0.000001:
            continue
        fc = center(face)
        if dot(n, sub(fc, solid_center)) < 0:
            return a, b, c
        return a, c, b
    return None

def make_side(side_id: int, face: List[Vec3], solid_center: Vec3, material: str, tex_scale: float) -> Optional[str]:
    n = face_normal_from_points(face)
    if n is None:
        return None

    pp = plane_points(face, solid_center)
    if pp is None:
        return None

    a, b, c = pp
    u, v = choose_texture_axes(n)

    return (
        "        side\n"
        "        {\n"
        f'            "id" "{side_id}"\n'
        f'            "plane" "({fmt(a)}) ({fmt(b)}) ({fmt(c)})"\n'
        f'            "material" "{material}"\n'
        f'            "uaxis" "[{u[0]:.6f} {u[1]:.6f} {u[2]:.6f} 0] {tex_scale}"\n'
        f'            "vaxis" "[{v[0]:.6f} {v[1]:.6f} {v[2]:.6f} 0] {tex_scale}"\n'
        '            "rotation" "0"\n'
        '            "lightmapscale" "16"\n'
        '            "smoothing_groups" "0"\n'
        "        }"
    )

def make_panel_solid(face_ids: List[int], verts: List[Vec3], solid_id: int, side_id: int, thickness: float, material: str, tex_scale: float):
    face = face_points(face_ids, verts)
    n = face_normal_from_points(face)

    if n is None:
        return "", side_id, False

    h = thickness * 0.5
    front = [add(v, mul(n, h)) for v in face]
    back = [sub(v, mul(n, h)) for v in face]
    solid_center = center(front + back)

    panel_faces: List[List[Vec3]] = []
    panel_faces.append(front)
    panel_faces.append(list(reversed(back)))

    for i in range(len(front)):
        j = (i + 1) % len(front)
        panel_faces.append([front[i], back[i], back[j], front[j]])

    sides: List[str] = []

    for f in panel_faces:
        s = make_side(side_id, f, solid_center, material, tex_scale)
        if s is None:
            return "", side_id, False
        sides.append(s)
        side_id += 1

    solid = (
        "    solid\n"
        "    {\n"
        f'        "id" "{solid_id}"\n'
        + "\n".join(sides) + "\n"
        "    }"
    )

    return solid, side_id, True

def wrap_entity(classname: str, entity_id: int, solids: List[str], alpha: int) -> str:
    body = "\n".join(solids)

    extra = ""
    if classname == "func_illusionary":
        extra = f'    "rendermode" "1"\n    "renderamt" "{alpha}"\n'

    return (
        "entity\n"
        "{\n"
        f'    "id" "{entity_id}"\n'
        f'    "classname" "{classname}"\n'
        + extra
        + body + "\n"
        "}"
    )

def write_vmf(path: str, solids: List[str], mode: str, skyname: str, alpha: int):
    world_solids: List[str] = []
    entities: List[str] = []

    if mode == "world":
        world_solids = solids
    else:
        entities.append(wrap_entity(mode, 2, solids, alpha))

    vmf = (
        '"versioninfo"\n'
        "{\n"
        '    "editorversion" "400"\n'
        '    "editorbuild" "0"\n'
        '    "mapversion" "1"\n'
        '    "formatversion" "100"\n'
        '    "prefab" "0"\n'
        "}\n"
        '"visgroups"\n'
        "{\n"
        "}\n"
        '"viewsettings"\n'
        "{\n"
        '    "bSnapToGrid" "1"\n'
        '    "bShowGrid" "1"\n'
        '    "bShowLogicalGrid" "0"\n'
        '    "nGridSpacing" "64"\n'
        '    "bShow3DGrid" "0"\n'
        "}\n"
        '"world"\n'
        "{\n"
        '    "id" "1"\n'
        '    "mapversion" "1"\n'
        '    "classname" "worldspawn"\n'
        f'    "skyname" "{skyname}"\n'
        + "\n".join(world_solids) + "\n"
        "}\n"
        + "\n".join(entities) + "\n"
        '"cameras"\n'
        "{\n"
        '    "activecamera" "-1"\n'
        "}\n"
        '"cordons"\n'
        "{\n"
        '    "active" "0"\n'
        "}\n"
    )

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(vmf)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--grid", type=float, default=1.0)
    ap.add_argument("--axis", choices=["xzy", "xyz", "source2", "unreal"], default="xzy")
    ap.add_argument("--thickness", type=float, default=4.0)
    ap.add_argument("--min-area", type=float, default=1.0)
    ap.add_argument("--material", default="DEV/DEV_MEASUREGENERIC01")
    ap.add_argument("--mode", choices=["func_illusionary", "func_detail", "world"], default="func_illusionary")
    ap.add_argument("--tex-scale", type=float, default=0.25)
    ap.add_argument("--skyname", default="painted")
    ap.add_argument("--alpha", type=int, default=160)
    ap.add_argument("--no-merge-triangles", action="store_true")
    ap.add_argument("--normal-tolerance", type=float, default=2.0)
    ap.add_argument("--rect-only", action="store_true")
    ap.add_argument("--rect-tolerance", type=float, default=8.0)
    args = ap.parse_args()

    if os.path.splitext(args.input)[1].lower() != ".obj":
        raise SystemExit("input must be .obj")

    verts, raw_faces = parse_obj(args.input, args.scale, args.grid, args.axis)

    faces: List[List[int]] = []
    for f in raw_faces:
        faces.extend(triangulate(f, verts, args.min_area))

    before_merge = len(faces)

    if not args.no_merge_triangles:
        faces = merge_triangles_to_quads(
            faces,
            verts,
            normal_tolerance_deg=args.normal_tolerance,
            rect_only=args.rect_only,
            rect_tolerance_deg=args.rect_tolerance,
        )

    solids: List[str] = []
    side_id = 10000
    solid_id = 1000
    skipped = 0

    for f in faces:
        solid, side_id, ok = make_panel_solid(
            f,
            verts,
            solid_id,
            side_id,
            args.thickness,
            args.material,
            args.tex_scale,
        )

        if ok:
            solids.append(solid)
            solid_id += 1
        else:
            skipped += 1

    write_vmf(args.output, solids, args.mode, args.skyname, args.alpha)

    print("done:", args.output)
    print("unique vertices:", len(verts))
    print("obj faces:", len(raw_faces))
    print("faces before merge:", before_merge)
    print("faces after merge:", len(faces))
    print("vmf panel brushes:", len(solids))
    print("skipped:", skipped)
    print("mode:", args.mode)

if __name__ == "__main__":
    main()
