import argparse
import math
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

Vec3 = Tuple[float, float, float]

@dataclass
class ObjSolid:
    name: str
    faces: List[List[Vec3]] = field(default_factory=list)

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

def center(points: List[Vec3]) -> Vec3:
    if not points:
        return (0.0, 0.0, 0.0)
    n = len(points)
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )

def same_point(a: Vec3, b: Vec3, eps: float = 0.01) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps and abs(a[2] - b[2]) <= eps

def clean_face(face: List[Vec3]) -> List[Vec3]:
    out: List[Vec3] = []
    for v in face:
        if not out or not same_point(out[-1], v):
            out.append(v)
    if len(out) >= 2 and same_point(out[0], out[-1]):
        out.pop()
    return out

def face_normal(face: List[Vec3]) -> Optional[Vec3]:
    if len(face) < 3:
        return None
    c = center(face)
    n = (0.0, 0.0, 0.0)
    for i in range(len(face)):
        a = sub(face[i], c)
        b = sub(face[(i + 1) % len(face)], c)
        n = add(n, cross(a, b))
    return norm(n)

def face_area(face: List[Vec3]) -> float:
    if len(face) < 3:
        return 0.0
    c = center(face)
    area = 0.0
    for i in range(len(face)):
        area += length(cross(sub(face[i], c), sub(face[(i + 1) % len(face)], c))) * 0.5
    return area

def snap_value(v: float, grid: float) -> float:
    if grid <= 0:
        return v
    return round(v / grid) * grid

def snap_vec(v: Vec3, grid: float) -> Vec3:
    return (snap_value(v[0], grid), snap_value(v[1], grid), snap_value(v[2], grid))

def blender_to_source(v: Vec3, scale: float, mode: str) -> Vec3:
    x, y, z = v
    if mode == "xzy":
        return (x * scale, -z * scale, y * scale)
    if mode == "xyz":
        return (x * scale, y * scale, z * scale)
    if mode == "unreal":
        return (x * scale, -y * scale, z * scale)
    return (x * scale, -z * scale, y * scale)

def parse_obj(path: str, scale: float, grid: float, axis: str, group_by: str) -> List[ObjSolid]:
    verts: List[Vec3] = []
    solids: List[ObjSolid] = []
    current = ObjSolid("world")

    def finish_current():
        nonlocal current
        if current.faces:
            solids.append(current)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    v = (float(parts[1]), float(parts[2]), float(parts[3]))
                    verts.append(snap_vec(blender_to_source(v, scale, axis), grid))
                continue

            if group_by == "object" and line.startswith("o "):
                finish_current()
                current = ObjSolid(line[2:].strip() or f"obj_{len(solids)}")
                continue

            if group_by == "group" and line.startswith("g "):
                finish_current()
                current = ObjSolid(line[2:].strip() or f"group_{len(solids)}")
                continue

            if line.startswith("f "):
                idxs: List[int] = []
                for token in line.split()[1:]:
                    vi = token.split("/")[0]
                    if not vi:
                        continue
                    n = int(vi)
                    if n < 0:
                        n = len(verts) + n + 1
                    idxs.append(n - 1)

                face = []
                for i in idxs:
                    if 0 <= i < len(verts):
                        face.append(verts[i])

                face = clean_face(face)
                if len(face) >= 3:
                    current.faces.append(face)

    finish_current()
    return solids

def solid_center(s: ObjSolid) -> Vec3:
    pts: List[Vec3] = []
    for face in s.faces:
        pts.extend(face)
    return center(pts)

def choose_plane_points(face: List[Vec3]) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    if len(face) < 3:
        return None
    a = face[0]
    for i in range(1, len(face) - 1):
        b = face[i]
        c = face[i + 1]
        if length(cross(sub(b, a), sub(c, a))) > 0.0001:
            return a, b, c
    return None

def hammer_plane(face: List[Vec3], csolid: Vec3) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    pts = choose_plane_points(face)
    if pts is None:
        return None

    a, b, c = pts
    n = cross(sub(b, a), sub(c, a))
    fc = center(face)

    if dot(n, sub(fc, csolid)) < 0:
        return a, b, c
    return a, c, b

def choose_texture_axes(n: Vec3) -> Tuple[Vec3, Vec3]:
    candidates = [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ]

    base = min(candidates, key=lambda a: abs(dot(a, n)))

    u = norm(cross(base, n))
    if u is None:
        u = (1.0, 0.0, 0.0)

    v = norm(cross(n, u))
    if v is None:
        v = (0.0, 1.0, 0.0)

    return u, v

def fmt(v: Vec3) -> str:
    return f"{v[0]:.3f} {v[1]:.3f} {v[2]:.3f}"

def make_side(side_id: int, face: List[Vec3], csolid: Vec3, material: str, tex_scale: float) -> Optional[str]:
    n = face_normal(face)
    if n is None:
        return None

    plane = hammer_plane(face, csolid)
    if plane is None:
        return None

    a, b, c = plane
    u, v = choose_texture_axes(n)

    return f'''        side
        {{
            "id" "{side_id}"
            "plane" "({fmt(a)}) ({fmt(b)}) ({fmt(c)})"
            "material" "{material}"
            "uaxis" "[{u[0]:.6f} {u[1]:.6f} {u[2]:.6f} 0] {tex_scale}"
            "vaxis" "[{v[0]:.6f} {v[1]:.6f} {v[2]:.6f} 0] {tex_scale}"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}'''

def make_vmf_solid(s: ObjSolid, solid_id: int, side_id: int, material: str, min_area: float, tex_scale: float, max_faces: int):
    faces = [clean_face(f) for f in s.faces]
    faces = [f for f in faces if len(f) >= 3 and face_area(f) >= min_area]

    if len(faces) < 4:
        return "", side_id, "too_few_faces"

    if len(faces) > max_faces:
        return "", side_id, "too_many_faces"

    csolid = center([v for face in faces for v in face])
    sides: List[str] = []

    for face in faces:
        txt = make_side(side_id, face, csolid, material, tex_scale)
        if txt is None:
            return "", side_id, "bad_face"
        sides.append(txt)
        side_id += 1

    solid = f'''    solid
    {{
        "id" "{solid_id}"
{chr(10).join(sides)}
    }}'''

    return solid, side_id, "ok"

def write_vmf(path: str, solids: List[ObjSolid], material: str, min_area: float, tex_scale: float, max_faces: int):
    vmf_solids: List[str] = []
    solid_id = 1000
    side_id = 10000
    stats = {}

    for s in solids:
        solid, side_id, status = make_vmf_solid(s, solid_id, side_id, material, min_area, tex_scale, max_faces)
        stats[status] = stats.get(status, 0) + 1

        if status == "ok":
            vmf_solids.append(solid)
            solid_id += 1

    vmf = f'''"versioninfo"
{{
    "editorversion" "400"
    "editorbuild" "0"
    "mapversion" "1"
    "formatversion" "100"
    "prefab" "0"
}}
"visgroups"
{{
}}
"viewsettings"
{{
    "bSnapToGrid" "1"
    "bShowGrid" "1"
    "bShowLogicalGrid" "0"
    "nGridSpacing" "64"
    "bShow3DGrid" "0"
}}
"world"
{{
    "id" "1"
    "mapversion" "1"
    "classname" "worldspawn"
    "skyname" "painted"
{chr(10).join(vmf_solids)}
}}
"cameras"
{{
    "activecamera" "-1"
}}
"cordons"
{{
    "active" "0"
}}
'''

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(vmf)

    print("done:", path)
    print("obj solids:", len(solids))
    print("vmf solids:", len(vmf_solids))
    print("stats:", stats)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--grid", type=float, default=1.0)
    ap.add_argument("--axis", choices=["xzy", "xyz", "unreal"], default="xzy")
    ap.add_argument("--group-by", choices=["object", "group"], default="object")
    ap.add_argument("--material", default="TOOLS/TOOLSNODRAW")
    ap.add_argument("--min-area", type=float, default=1.0)
    ap.add_argument("--tex-scale", type=float, default=0.25)
    ap.add_argument("--max-faces", type=int, default=128)
    args = ap.parse_args()

    if os.path.splitext(args.input)[1].lower() != ".obj":
        raise SystemExit("input must be .obj")

    solids = parse_obj(
        args.input,
        scale=args.scale,
        grid=args.grid,
        axis=args.axis,
        group_by=args.group_by,
    )

    write_vmf(
        args.output,
        solids=solids,
        material=args.material,
        min_area=args.min_area,
        tex_scale=args.tex_scale,
        max_faces=args.max_faces,
    )

if __name__ == "__main__":
    main()
