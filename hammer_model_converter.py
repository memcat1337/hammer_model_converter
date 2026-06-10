import sys
import shlex
import json
import runpy
import math
import tempfile
import io
import contextlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

from PySide6.QtCore import QProcess, Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QDragEnterEvent, QDropEvent, QFont, QColor, QPalette, QPainter,
    QPen, QBrush, QPolygonF, QMouseEvent, QWheelEvent, QMatrix4x4, QSurfaceFormat
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QTextEdit, QGridLayout, QHBoxLayout, QVBoxLayout, QMessageBox,
    QScrollArea, QFrame, QSizePolicy, QButtonGroup, QDockWidget, QStatusBar
)

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLBuffer, QOpenGLVertexArrayObject, QOpenGLShader
    OPENGL_PREVIEW_AVAILABLE = True
except Exception:
    QOpenGLWidget = QWidget
    QOpenGLShaderProgram = None
    QOpenGLBuffer = None
    QOpenGLVertexArrayObject = None
    QOpenGLShader = None
    OPENGL_PREVIEW_AVAILABLE = False

APP_TITLE = "Конвертер моделей Hammer"
CONFIG_NAME = "hammer_model_converter_config.json"

Vec3 = Tuple[float, float, float]
Edge = Tuple[int, int]

STYLE = """
QMainWindow, QWidget {
    background: #2f2f2f;
    color: #cfcfcf;
    font-family: Segoe UI;
    font-size: 9pt;
}
QFrame#LeftPanel {
    background: #303030;
    border-right: 1px solid #111111;
}
QFrame#RightPanel {
    background: #050505;
}
QFrame#PreviewToolbar {
    background: #151515;
    border: 1px solid #202020;
}
QFrame#BottomStatus {
    background: #aa1414;
    border-top: 1px solid #5b0000;
}
QDockWidget {
    background: #2f2f2f;
    color: #ffffff;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background: #151515;
    color: #ffffff;
    font-weight: 700;
    padding: 3px 6px;
    text-align: center;
}
QDockWidget::separator {
    background: #555555;
    width: 4px;
    height: 4px;
}
QStatusBar {
    background: #3a3a3a;
    color: #ffffff;
    border-top: 1px solid #1f1f1f;
}
QLabel#PanelCaption {
    background: #151515;
    color: #ffffff;
    font-weight: 700;
    padding: 2px 4px;
    min-height: 14px;
}
QLabel#SectionTitle {
    background: #151515;
    color: #ffffff;
    font-weight: 700;
    padding: 3px 6px;
    min-height: 16px;
}
QLabel#SmallLabel {
    color: #c7c7c7;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background: #242424;
    color: #e1e1e1;
    border: 1px solid #565656;
    border-radius: 2px;
    min-height: 20px;
    padding: 1px 4px;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #d88428;
}
QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {
    background: #252525;
    color: #6d6d6d;
    border: 1px solid #3f3f3f;
}
QPushButton {
    background: #3b3b3b;
    color: #dddddd;
    border: 1px solid #6b747d;
    border-radius: 3px;
    min-height: 22px;
    padding: 2px 8px;
}
QPushButton:hover {
    background: #4b5661;
    color: #ffffff;
    border: 1px solid #8e9bab;
}
QPushButton:pressed {
    background: #2d3339;
}
QPushButton:checked {
    background: #404040;
    color: #e89036;
    border: 2px solid #d88428;
}
QPushButton:disabled {
    background: #333333;
    color: #777777;
    border: 1px solid #555555;
}
QPushButton#BuildButton:hover {
    background: #435063;
}
QPushButton#AbortButton:hover {
    background: #8d2525;
    border: 1px solid #bd3a3a;
}
QCheckBox {
    color: #cfcfcf;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #656565;
    background: #2a2a2a;
}
QCheckBox::indicator:checked {
    background: #5f6a76;
    border: 1px solid #aeb8c3;
}
QTextEdit {
    background: #000000;
    color: #f0f0f0;
    border: 1px solid #161616;
    selection-background-color: #555555;
    selection-color: #ffffff;
}
QScrollArea {
    border: none;
    background: #303030;
}
QScrollBar:vertical {
    background: #111111;
    width: 14px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #4a4a4a;
    min-height: 24px;
    border: 1px solid #686868;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background: #252525;
    height: 14px;
    border: 1px solid #555555;
}
"""

# ----------------------------- geometry helpers -----------------------------

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


def clean_face_points(face: List[Vec3]) -> List[Vec3]:
    out: List[Vec3] = []
    for v in face:
        if not out or not same_point(out[-1], v):
            out.append(v)
    if len(out) >= 2 and same_point(out[0], out[-1]):
        out.pop()
    return out


def face_normal_points(face: List[Vec3]) -> Optional[Vec3]:
    if len(face) < 3:
        return None
    c = center(face)
    n = (0.0, 0.0, 0.0)
    for i in range(len(face)):
        a = sub(face[i], c)
        b = sub(face[(i + 1) % len(face)], c)
        n = add(n, cross(a, b))
    return norm(n)


def face_area_points(face: List[Vec3]) -> float:
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


def face_points(face: List[int], verts: List[Vec3]) -> List[Vec3]:
    return [verts[i] for i in face]


def face_normal_ids(face: List[int], verts: List[Vec3]) -> Optional[Vec3]:
    return face_normal_points(face_points(face, verts))


def face_area_ids(face: List[int], verts: List[Vec3]) -> float:
    return face_area_points(face_points(face, verts))


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
    n2 = face_normal_ids(ordered, verts)
    if n2 is not None and dot(n2, n) < 0:
        ordered.reverse()
    return ordered


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


def merge_triangles_to_quads(
    faces: List[List[int]],
    verts: List[Vec3],
    normal_tolerance_deg: float,
    rect_only: bool,
    rect_tolerance_deg: float,
) -> List[List[int]]:
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
            used.add(ti)
            continue

        best = None
        for i in range(3):
            e = edge_key(t[i], t[(i + 1) % 3])
            for tj in edge_map.get(e, []):
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


def triangulate_face_ids(face: List[int], verts: List[Vec3], min_area: float) -> List[List[int]]:
    if len(face) <= 4:
        return [face] if face_area_ids(face, verts) >= min_area else []
    out: List[List[int]] = []
    for i in range(1, len(face) - 1):
        t = [face[0], face[i], face[i + 1]]
        if face_area_ids(t, verts) >= min_area:
            out.append(t)
    return out


def make_panel_faces(face: List[Vec3], thickness: float) -> List[List[Vec3]]:
    n = face_normal_points(face)
    if n is None:
        return []
    h = thickness * 0.5
    front = [add(v, mul(n, h)) for v in face]
    back = [sub(v, mul(n, h)) for v in face]
    panel_faces: List[List[Vec3]] = [front, list(reversed(back))]
    for i in range(len(front)):
        j = (i + 1) % len(front)
        panel_faces.append([front[i], back[i], back[j], front[j]])
    return panel_faces


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


def outward_plane_points(face: List[Vec3], solid_center: Vec3) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    pts = choose_plane_points(face)
    if pts is None:
        return None
    a, b, c = pts
    n = cross(sub(b, a), sub(c, a))
    fc = center(face)
    if dot(n, sub(fc, solid_center)) < 0:
        return a, b, c
    return a, c, b


def plane_from_points(a: Vec3, b: Vec3, c: Vec3) -> Optional[Tuple[Vec3, float]]:
    n = norm(cross(sub(b, a), sub(c, a)))
    if n is None:
        return None
    return n, dot(n, a)


def det3(m: List[List[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def intersect_three_planes(p1, p2, p3) -> Optional[Vec3]:
    n1, d1 = p1
    n2, d2 = p2
    n3, d3 = p3
    a = [list(n1), list(n2), list(n3)]
    det_a = det3(a)
    if abs(det_a) < 0.000001:
        return None
    mx = [[d1, a[0][1], a[0][2]], [d2, a[1][1], a[1][2]], [d3, a[2][1], a[2][2]]]
    my = [[a[0][0], d1, a[0][2]], [a[1][0], d2, a[1][2]], [a[2][0], d3, a[2][2]]]
    mz = [[a[0][0], a[0][1], d1], [a[1][0], a[1][1], d2], [a[2][0], a[2][1], d3]]
    return (det3(mx) / det_a, det3(my) / det_a, det3(mz) / det_a)


def point_inside_planes(p: Vec3, planes: List[Tuple[Vec3, float]], eps: float = 0.03) -> bool:
    for n, d in planes:
        if dot(n, p) > d + eps:
            return False
    return True


def unique_points(points: List[Vec3], eps: float = 0.05) -> List[Vec3]:
    out: List[Vec3] = []
    for p in points:
        if not any(same_point(p, q, eps) for q in out):
            out.append(p)
    return out


def reconstruct_convex_solid_faces(source_faces: List[List[Vec3]]) -> Tuple[List[List[Vec3]], str]:
    faces = [clean_face_points(f) for f in source_faces if len(clean_face_points(f)) >= 3]
    if len(faces) < 4:
        return [], "too_few_faces"

    csolid = center([v for f in faces for v in f])
    planes: List[Tuple[Vec3, float]] = []
    for f in faces:
        pts = outward_plane_points(f, csolid)
        if pts is None:
            return [], "bad_face"
        plane = plane_from_points(*pts)
        if plane is None:
            return [], "bad_face"
        planes.append(plane)

    out_faces: List[List[Vec3]] = []
    nplanes = len(planes)
    for i, (n, d) in enumerate(planes):
        pts: List[Vec3] = []
        for j in range(nplanes):
            if j == i:
                continue
            for k in range(j + 1, nplanes):
                if k == i:
                    continue
                p = intersect_three_planes(planes[i], planes[j], planes[k])
                if p is not None and point_inside_planes(p, planes):
                    pts.append(p)
        pts = unique_points(pts)
        if len(pts) >= 3:
            ids = list(range(len(pts)))
            ordered_ids = order_polygon(ids, pts, n)
            # Для отрисовки нужна та же наружная ориентация, что и у VMF plane.
            out_faces.append([pts[idx] for idx in ordered_ids])

    if len(out_faces) < 4:
        return [], "bad_solid"
    return out_faces, "ok"


# ----------------------------- preview data build ----------------------------

class PreviewMesh:
    MAX_DRAW_FACES = 6000

    def __init__(self):
        self.faces: List[Tuple[List[Vec3], int]] = []
        self.message = "Нет модели"
        self.stats = ""
        self.scale_value = 1.0
        # Размер базовой модели, относительно которого рисуется предпросмотр.
        # Нужен, чтобы --scale визуально влиял только на конвертацию,
        # а не скрывался автоматическим вписыванием каждого результата в окно.
        self.view_size: Optional[float] = None
        self.total_faces = 0
        self.limited = False

    def add_face(self, pts: List[Vec3], brush_id: int):
        pts = clean_face_points(pts)
        if len(pts) >= 3:
            self.total_faces += 1
            if len(self.faces) < self.MAX_DRAW_FACES:
                self.faces.append((pts, brush_id))
            else:
                self.limited = True

    def append_limit_note(self):
        if self.limited:
            self.stats += f" | показано {len(self.faces)} из {self.total_faces} граней"

    def all_points(self) -> List[Vec3]:
        pts: List[Vec3] = []
        for f, _ in self.faces:
            pts.extend(f)
        return pts


def parse_obj_as_solids(path: str, scale: float, grid: float, axis: str, group_by: str) -> List[Tuple[str, List[List[Vec3]]]]:
    verts: List[Vec3] = []
    solids: List[Tuple[str, List[List[Vec3]]]] = []
    current_name = "world"
    current_faces: List[List[Vec3]] = []

    def finish_current():
        nonlocal current_name, current_faces
        if current_faces:
            solids.append((current_name, current_faces))
            current_faces = []

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
                current_name = line[2:].strip() or f"obj_{len(solids)}"
                continue
            if group_by == "group" and line.startswith("g "):
                finish_current()
                current_name = line[2:].strip() or f"group_{len(solids)}"
                continue
            if line.startswith("f "):
                face: List[Vec3] = []
                for token in line.split()[1:]:
                    vi = token.split("/")[0]
                    if not vi:
                        continue
                    n = int(vi)
                    if n < 0:
                        n = len(verts) + n + 1
                    idx = n - 1
                    if 0 <= idx < len(verts):
                        face.append(verts[idx])
                face = clean_face_points(face)
                if len(face) >= 3:
                    current_faces.append(face)
    finish_current()
    return solids


def parse_obj_as_indexed_faces(path: str, scale: float, grid: float, axis: str) -> Tuple[List[Vec3], List[List[int]]]:
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
                    v = snap_vec(blender_to_source(v, scale, axis), grid)
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


def build_source_preview(path: str, scale: float, grid: float, axis: str) -> PreviewMesh:
    mesh = PreviewMesh()
    mesh.scale_value = scale
    solids = parse_obj_as_solids(path, scale, grid, axis, "object")
    total_faces = sum(len(faces) for _, faces in solids)
    # Если OBJ слишком тяжёлый, берём равномерную выборку граней, чтобы GUI не зависал.
    step = max(1, math.ceil(total_faces / mesh.MAX_DRAW_FACES))
    face_counter = 0
    brush_id = 0
    for _, faces in solids:
        for f in faces:
            if face_counter % step == 0:
                mesh.add_face(f, brush_id)
            else:
                mesh.total_faces += 1
                mesh.limited = True
            face_counter += 1
        brush_id += 1
    mesh.message = "Исходная OBJ-модель"
    mesh.stats = f"objects={len(solids)}, faces={total_faces}"
    append_bbox_stats(mesh)
    mesh.append_limit_note()
    return mesh


def build_brush_preview(path: str, scale: float, grid: float, axis: str, group_by: str, min_area: float, max_faces: int) -> PreviewMesh:
    mesh = PreviewMesh()
    mesh.scale_value = scale
    solids = parse_obj_as_solids(path, scale, grid, axis, group_by)
    stats = {"ok": 0, "too_few_faces": 0, "too_many_faces": 0, "bad_face": 0, "bad_solid": 0}
    brush_id = 0
    for _, faces in solids:
        cleaned = [clean_face_points(f) for f in faces]
        filtered = [f for f in cleaned if len(f) >= 3 and face_area_points(f) >= min_area]
        if len(filtered) < 4:
            stats["too_few_faces"] += 1
            continue
        if len(filtered) > max_faces:
            stats["too_many_faces"] += 1
            continue

        # Важно: VMF хранит не вершины, а плоскости. Hammer пересобирает браш
        # как пересечение полупространств. Поэтому предпросмотр тоже реконструирует
        # итоговый convex-solid по плоскостям, а не просто рисует исходные полигоны OBJ.
        solid_faces, status = reconstruct_convex_solid_faces(filtered)
        stats[status] = stats.get(status, 0) + 1
        if status != "ok":
            continue
        for f in solid_faces:
            mesh.add_face(f, brush_id)
        brush_id += 1

    skipped = sum(v for k, v in stats.items() if k != "ok")
    mesh.message = "Предпросмотр: выпуклые формы — браши"
    mesh.stats = f"solids={len(solids)}, vmf_solids={stats['ok']}, skipped={skipped}"
    if stats.get("bad_face") or stats.get("bad_solid"):
        mesh.stats += f" | bad={stats.get('bad_face', 0) + stats.get('bad_solid', 0)}"
    append_bbox_stats(mesh)
    mesh.append_limit_note()
    return mesh


def build_triangle_preview(
    path: str,
    scale: float,
    grid: float,
    axis: str,
    min_area: float,
    thickness: float,
    no_merge: bool,
    normal_tolerance: float,
    rect_only: bool,
    rect_tolerance: float,
) -> PreviewMesh:
    mesh = PreviewMesh()
    mesh.scale_value = scale
    verts, raw_faces = parse_obj_as_indexed_faces(path, scale, grid, axis)
    faces: List[List[int]] = []
    for f in raw_faces:
        faces.extend(triangulate_face_ids(f, verts, min_area))
    before_merge = len(faces)
    if not no_merge:
        faces = merge_triangles_to_quads(faces, verts, normal_tolerance, rect_only, rect_tolerance)

    skipped = 0
    brush_id = 0
    # Один panel-brush даёт 5-6 видимых граней. Чтобы режим треугольников не
    # блокировал интерфейс, тяжёлые модели показываются равномерной выборкой.
    estimated_draw_faces = max(1, len(faces) * 6)
    step = max(1, math.ceil(estimated_draw_faces / mesh.MAX_DRAW_FACES))
    for f in faces:
        panel = make_panel_faces(face_points(f, verts), thickness)
        if not panel:
            skipped += 1
            continue
        if brush_id % step == 0:
            for pf in panel:
                mesh.add_face(pf, brush_id)
        else:
            mesh.total_faces += len(panel)
            mesh.limited = True
        brush_id += 1
    mesh.message = "Предпросмотр: 1 треугольник = 1 браш"
    mesh.stats = f"obj_faces={len(raw_faces)}, before_merge={before_merge}, after_merge={len(faces)}, panel_brushes={brush_id}, skipped={skipped}"
    append_bbox_stats(mesh)
    mesh.append_limit_note()
    return mesh




def mesh_bbox_size(mesh: PreviewMesh) -> float:
    pts = mesh.all_points()
    if not pts:
        return 1.0
    min_x = min(p[0] for p in pts); max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts); max_y = max(p[1] for p in pts)
    min_z = min(p[2] for p in pts); max_z = max(p[2] for p in pts)
    return max(max_x - min_x, max_y - min_y, max_z - min_z, 1.0)


def append_bbox_stats(mesh: PreviewMesh):
    pts = mesh.all_points()
    if not pts:
        return
    min_x = min(p[0] for p in pts); max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts); max_y = max(p[1] for p in pts)
    min_z = min(p[2] for p in pts); max_z = max(p[2] for p in pts)
    mesh.stats += f" | размер Hammer: {max_x-min_x:.0f} x {max_y-min_y:.0f} x {max_z-min_z:.0f}"


def apply_reference_view_size(mesh: PreviewMesh, source_path: str, axis: str):
    """Фиксирует визуальный масштаб относительно исходной OBJ-модели.

    Исходная модель всегда строится с scale=1 и grid=0. Конвертация строится
    с текущим --scale, но рисуется в том же визуальном масштабе. За счёт этого
    изменение --scale видно только во вкладке «Конвертация».
    """
    try:
        ref = build_source_preview(source_path, 1.0, 0.0, axis)
        mesh.view_size = mesh_bbox_size(ref)
    except Exception:
        mesh.view_size = None


def parse_vmf_plane_points(line: str) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    # line format: "plane" "(x y z) (x y z) (x y z)"
    if '"plane"' not in line:
        return None
    import re
    nums = re.findall(r"\((-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\)", line)
    if len(nums) != 3:
        return None
    pts = []
    for n in nums:
        pts.append((float(n[0]), float(n[1]), float(n[2])))
    return pts[0], pts[1], pts[2]


def parse_vmf_solids_as_faces(path: str) -> Tuple[List[List[List[Vec3]]], int]:
    """Читает реальные VMF solid-плоскости и пересобирает их в грани для предпросмотра.

    Важно: в VMF ориентация plane может отличаться от той, которую ожидает
    математический реконструктор. Поэтому плоскости дополнительно
    переориентируются относительно центра solid-блока. Это исправляет случай,
    когда VMF создан успешно, но предпросмотр показывает пустое окно.
    """
    solids_raw: List[List[Tuple[Vec3, Vec3, Vec3]]] = []
    lines = Path(path).read_text(encoding='utf-8', errors='ignore').splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == 'solid':
            block_lines: List[str] = []
            brace = 0
            started = False
            i += 1
            while i < len(lines):
                t = lines[i]
                if '{' in t:
                    brace += t.count('{')
                    started = True
                if started:
                    block_lines.append(t)
                if '}' in t:
                    brace -= t.count('}')
                    if started and brace <= 0:
                        break
                i += 1

            raw_planes: List[Tuple[Vec3, Vec3, Vec3]] = []
            for bl in block_lines:
                pp = parse_vmf_plane_points(bl)
                if pp is not None:
                    raw_planes.append(pp)
            if len(raw_planes) >= 4:
                solids_raw.append(raw_planes)
        i += 1

    solids_faces: List[List[List[Vec3]]] = []
    bad = 0

    for raw_planes in solids_raw:
        all_pp: List[Vec3] = []
        for a, b, c in raw_planes:
            all_pp.extend([a, b, c])
        csolid = center(all_pp)

        planes: List[Tuple[Vec3, float]] = []
        for a, b, c in raw_planes:
            plane = plane_from_points(a, b, c)
            if plane is None:
                continue
            n, d = plane
            # Для пересечения полупространств принимаем правило:
            # внутренняя область solid находится там, где dot(n,p) <= d.
            # Если центр solid оказался снаружи, разворачиваем плоскость.
            if dot(n, csolid) > d:
                n = (-n[0], -n[1], -n[2])
                d = -d
            planes.append((n, d))

        if len(planes) < 4:
            bad += 1
            continue

        out_faces: List[List[Vec3]] = []
        for pi, (n, d) in enumerate(planes):
            pts: List[Vec3] = []
            for j in range(len(planes)):
                if j == pi:
                    continue
                for k in range(j + 1, len(planes)):
                    if k == pi:
                        continue
                    p = intersect_three_planes(planes[pi], planes[j], planes[k])
                    if p is not None and point_inside_planes(p, planes, eps=0.12):
                        pts.append(p)
            pts = unique_points(pts, eps=0.12)
            if len(pts) >= 3:
                ids = list(range(len(pts)))
                ordered = order_polygon(ids, pts, n)
                out_faces.append([pts[idx] for idx in ordered])

        if len(out_faces) >= 4:
            solids_faces.append(out_faces)
        else:
            bad += 1

    return solids_faces, bad

def run_converter_script_to_temp(script: str, argv: List[str]) -> str:
    old_argv = sys.argv[:]
    buf = io.StringIO()
    try:
        sys.argv = [str(script)] + argv
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 0
                if code not in (0, None):
                    raise RuntimeError(f"converter exited with code {code}\n{buf.getvalue()}")
    finally:
        sys.argv = old_argv
    return buf.getvalue()


def build_real_converted_preview(
    script: str,
    input_path: str,
    mode: str,
    scale: float,
    grid: float,
    axis: str,
    material: str,
    min_area: float,
    tex_scale: float,
    group_by: str,
    max_faces: int,
    thickness: float,
    tri_mode: str,
    skyname: str,
    alpha: int,
    no_merge: bool,
    normal_tolerance: float,
    rect_only: bool,
    rect_tolerance: float,
) -> PreviewMesh:
    mesh = PreviewMesh()
    mesh.scale_value = scale
    with tempfile.TemporaryDirectory(prefix='hmc_preview_') as td:
        out_vmf = str(Path(td) / 'preview.vmf')
        args = [
            input_path, out_vmf,
            '--scale', str(scale),
            '--grid', str(grid),
            '--axis', axis,
            '--material', material or 'TOOLS/TOOLSNODRAW',
            '--min-area', str(min_area),
            '--tex-scale', str(tex_scale),
        ]
        if mode == 'brushes':
            args += ['--group-by', group_by, '--max-faces', str(max_faces)]
        else:
            args += [
                '--thickness', str(thickness),
                '--mode', tri_mode,
                '--skyname', skyname or 'painted',
                '--alpha', str(alpha),
                '--normal-tolerance', str(normal_tolerance),
                '--rect-tolerance', str(rect_tolerance),
            ]
            if no_merge:
                args.append('--no-merge-triangles')
            if rect_only:
                args.append('--rect-only')
        log = run_converter_script_to_temp(script, args)
        solids_faces, bad = parse_vmf_solids_as_faces(out_vmf)

    for bid, faces in enumerate(solids_faces):
        for f in faces:
            mesh.add_face(f, bid)
    mesh.message = 'Реальный предпросмотр VMF: ' + ('выпуклые формы — браши' if mode == 'brushes' else '1 треугольник = 1 браш')
    mesh.stats = f'vmf_solids={len(solids_faces)}, bad_preview_solids={bad}'
    append_bbox_stats(mesh)
    mesh.append_limit_note()
    return mesh

# ----------------------------- widgets -----------------------------

class DropLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setPlaceholderText("перетащи .obj сюда")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".obj"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".obj"):
                self.setText(p)
                event.acceptProposedAction()
                return
        event.ignore()


class Section(QWidget):
    def __init__(self, title):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        head = QLabel(title)
        head.setObjectName("SectionTitle")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(5, 4, 5, 8)
        self.grid.setHorizontalSpacing(7)
        self.grid.setVerticalSpacing(5)
        root.addWidget(head)
        root.addWidget(self.body)
        self._row = 0

    def add_row(self, text, widget, button=None):
        label = QLabel(text)
        label.setObjectName("SmallLabel")
        label.setMinimumWidth(108)
        self.grid.addWidget(label, self._row, 0)
        self.grid.addWidget(widget, self._row, 1)
        if button is not None:
            self.grid.addWidget(button, self._row, 2)
        else:
            spacer = QLabel("")
            spacer.setFixedWidth(1)
            self.grid.addWidget(spacer, self._row, 2)
        self._row += 1

    def add_full(self, widget):
        self.grid.addWidget(widget, self._row, 0, 1, 3)
        self._row += 1


class PreviewWidget(QOpenGLWidget):
    """GPU-предпросмотр на QOpenGLWidget.

    Геометрия один раз преобразуется в треугольники и загружается в VBO.
    При вращении камеры CPU больше не пересчитывает каждую вершину: меняется
    только матрица MVP, а отрисовку выполняет видеокарта.
    """

    GL_COLOR_BUFFER_BIT = 0x00004000
    GL_DEPTH_BUFFER_BIT = 0x00000100
    GL_DEPTH_TEST = 0x0B71
    GL_CULL_FACE = 0x0B44
    GL_BLEND = 0x0BE2
    GL_SRC_ALPHA = 0x0302
    GL_ONE_MINUS_SRC_ALPHA = 0x0303
    GL_LEQUAL = 0x0203
    GL_FLOAT = 0x1406
    GL_TRIANGLES = 0x0004
    GL_LINES = 0x0001

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(340)
        self.setMouseTracking(True)
        self.mesh = PreviewMesh()
        self.display_mode = "source"  # source / converted
        self.color_mode = "gray"      # gray / brushes
        self.auto_rotate = False
        self.rot_x = -22.0
        self.rot_y = 35.0
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_mouse = None
        self.bg = QColor("#000000")
        self.grid_pen = QPen(QColor(40, 40, 40), 1)

        self.gl = None
        self.program = None
        self.vbo_tri = None
        self.vbo_lines = None
        self.vao_tri = None
        self.vao_lines = None
        self.triangle_vertex_count = 0
        self.line_vertex_count = 0
        self.gpu_ready = False
        self.gpu_dirty = True
        self.gpu_error = ""
        self.model_center = (0.0, 0.0, 0.0)
        self.own_size = 1.0
        self.mesh_view_size = 1.0

        # Dock-анимации отключены. Автоповорот предпросмотра включается только ПКМ.
        self.rotate_timer = QTimer(self)
        self.rotate_timer.setInterval(33)  # около 30 FPS только в режиме автоповорота
        self.rotate_timer.timeout.connect(self.tick)

    def set_mesh(self, mesh: PreviewMesh):
        self.mesh = mesh
        self.gpu_dirty = True
        self.update()

    def set_color_mode(self, mode: str):
        self.color_mode = mode
        self.gpu_dirty = True
        self.update()

    def set_auto_rotate(self, enabled: bool):
        self.auto_rotate = enabled
        if enabled:
            if not self.rotate_timer.isActive():
                self.rotate_timer.start()
        else:
            if self.rotate_timer.isActive():
                self.rotate_timer.stop()
        self.update()

    def tick(self):
        if self.auto_rotate and self.last_mouse is None:
            self.rot_y += 0.25
            if self.rot_y > 360.0:
                self.rot_y -= 360.0
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse = event.position()
            self.set_auto_rotate(False)
        elif event.button() == Qt.MouseButton.RightButton:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.rot_x = -22.0
                self.rot_y = 35.0
                self.zoom = 1.0
                self.pan_x = 0.0
                self.pan_y = 0.0
                self.set_auto_rotate(False)
            else:
                self.set_auto_rotate(not self.auto_rotate)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.last_mouse is None:
            return
        p = event.position()
        dx = p.x() - self.last_mouse.x()
        dy = p.y() - self.last_mouse.y()
        self.rot_y += dx * 0.45
        self.rot_x += dy * 0.45
        self.rot_x = max(-89.0, min(89.0, self.rot_x))
        self.last_mouse = p
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.last_mouse = None

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom *= 1.12
        else:
            self.zoom /= 1.12
        self.zoom = max(0.05, min(80.0, self.zoom))
        self.update()

    def initializeGL(self):
        if not OPENGL_PREVIEW_AVAILABLE:
            self.gpu_error = "Qt OpenGL недоступен. Проверь установку PySide6."
            return
        try:
            self.gl = self.context().functions()
            self.gl.initializeOpenGLFunctions()
            self.gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            self.gl.glEnable(self.GL_DEPTH_TEST)
            self.gl.glDepthFunc(self.GL_LEQUAL)
            self.gl.glEnable(self.GL_BLEND)
            self.gl.glBlendFunc(self.GL_SRC_ALPHA, self.GL_ONE_MINUS_SRC_ALPHA)

            self.program = QOpenGLShaderProgram(self)
            self.program.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex,
                """
                attribute highp vec3 a_position;
                attribute lowp vec3 a_color;
                uniform highp mat4 u_mvp;
                varying lowp vec3 v_color;
                void main() {
                    gl_Position = u_mvp * vec4(a_position, 1.0);
                    v_color = a_color;
                }
                """
            )
            self.program.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment,
                """
                varying lowp vec3 v_color;
                void main() {
                    gl_FragColor = vec4(v_color, 1.0);
                }
                """
            )
            self.program.bindAttributeLocation("a_position", 0)
            self.program.bindAttributeLocation("a_color", 1)
            if not self.program.link():
                self.gpu_error = "Ошибка компиляции OpenGL shader: " + self.program.log()
                return

            self.vao_tri = QOpenGLVertexArrayObject(self)
            self.vao_tri.create()
            self.vbo_tri = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self.vbo_tri.create()

            self.vao_lines = QOpenGLVertexArrayObject(self)
            self.vao_lines.create()
            self.vbo_lines = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self.vbo_lines.create()

            self.gpu_ready = True
            self.gpu_dirty = True
        except Exception as e:
            self.gpu_ready = False
            self.gpu_error = f"Ошибка инициализации OpenGL: {e}"

    def resizeGL(self, w: int, h: int):
        if self.gl:
            self.gl.glViewport(0, 0, max(1, w), max(1, h))

    def brush_rgb(self, brush_id: int, shade: float) -> Tuple[float, float, float]:
        if self.color_mode == "gray":
            v = max(55, min(220, 150 * shade)) / 255.0
            return (v, v, v)
        palette = [
            (220, 80, 80), (80, 190, 90), (80, 130, 230),
            (220, 190, 70), (180, 90, 220), (80, 200, 210),
            (230, 130, 60), (150, 220, 90), (220, 90, 150),
        ]
        r, g, b = palette[brush_id % len(palette)]
        return (
            max(25, min(255, r * shade)) / 255.0,
            max(25, min(255, g * shade)) / 255.0,
            max(25, min(255, b * shade)) / 255.0,
        )

    def normal_to_gl(self, n: Vec3) -> Vec3:
        return (n[0], n[2], n[1])

    def point_to_gl(self, p: Vec3, c: Vec3) -> Vec3:
        # Source/Hammer: X — вправо, Y — глубина, Z — высота.
        # OpenGL-буфер: X — вправо, Y — высота, Z — глубина.
        return (p[0] - c[0], p[2] - c[2], p[1] - c[1])

    def rebuild_gpu_buffers(self):
        if not self.gpu_ready or not self.program:
            return

        points = self.mesh.all_points()
        if not points:
            self.triangle_vertex_count = 0
            self.line_vertex_count = 0
            return

        c = center(points)
        self.model_center = c
        min_x = min(p[0] for p in points); max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points); max_y = max(p[1] for p in points)
        min_z = min(p[2] for p in points); max_z = max(p[2] for p in points)
        self.own_size = max(max_x - min_x, max_y - min_y, max_z - min_z, 1.0)
        self.mesh_view_size = self.mesh.view_size if self.mesh.view_size else self.own_size

        light = norm((0.35, 0.85, 0.45)) or (0.0, 1.0, 0.0)
        tri_floats: List[float] = []
        line_floats: List[float] = []
        black = (0.04, 0.04, 0.04)

        for face, brush_id in self.mesh.faces:
            clean = clean_face_points(face)
            if len(clean) < 3:
                continue
            n = face_normal_points(clean) or (0.0, 0.0, 1.0)
            ngl = norm(self.normal_to_gl(n)) or (0.0, 1.0, 0.0)
            shade = 0.45 + 0.55 * max(0.0, abs(dot(ngl, light)))
            color = self.brush_rgb(brush_id, shade)
            gl_pts = [self.point_to_gl(p, c) for p in clean]

            # face -> triangle fan
            for i in range(1, len(gl_pts) - 1):
                for v in (gl_pts[0], gl_pts[i], gl_pts[i + 1]):
                    tri_floats.extend([v[0], v[1], v[2], color[0], color[1], color[2]])

            # outline
            for i in range(len(gl_pts)):
                a = gl_pts[i]
                b = gl_pts[(i + 1) % len(gl_pts)]
                line_floats.extend([a[0], a[1], a[2], black[0], black[1], black[2]])
                line_floats.extend([b[0], b[1], b[2], black[0], black[1], black[2]])

        import array
        tri_arr = array.array('f', tri_floats)
        line_arr = array.array('f', line_floats)
        self.triangle_vertex_count = len(tri_floats) // 6
        self.line_vertex_count = len(line_floats) // 6

        self.vbo_tri.bind()
        self.vbo_tri.allocate(tri_arr.tobytes(), len(tri_arr) * 4)
        self.vbo_tri.release()

        self.vbo_lines.bind()
        self.vbo_lines.allocate(line_arr.tobytes(), len(line_arr) * 4)
        self.vbo_lines.release()

        self.gpu_dirty = False

    def configure_attributes(self, vbo):
        stride = 6 * 4
        self.program.enableAttributeArray(0)
        self.program.setAttributeBuffer(0, self.GL_FLOAT, 0, 3, stride)
        self.program.enableAttributeArray(1)
        self.program.setAttributeBuffer(1, self.GL_FLOAT, 3 * 4, 3, stride)

    def make_mvp(self) -> QMatrix4x4:
        w = max(1, self.width())
        h = max(1, self.height())
        aspect = w / h
        view_size = max(self.mesh_view_size, 1.0)
        half = view_size / (2.0 * 0.72 * max(self.zoom, 0.001))

        proj = QMatrix4x4()
        proj.ortho(-half * aspect, half * aspect, -half, half, -view_size * 20.0, view_size * 20.0)

        model = QMatrix4x4()
        model.translate(
            (self.pan_x / max(1.0, w)) * half * aspect * 2.0,
            -(self.pan_y / max(1.0, h)) * half * 2.0,
            0.0,
        )
        model.rotate(self.rot_x, 1.0, 0.0, 0.0)
        model.rotate(self.rot_y, 0.0, 1.0, 0.0)
        return proj * model

    def paintGL(self):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg)
        self.draw_background_grid(painter)
        painter.beginNativePainting()

        try:
            if self.gl:
                self.gl.glClear(self.GL_DEPTH_BUFFER_BIT)

            if self.gpu_ready and self.mesh.faces:
                if self.gpu_dirty:
                    self.rebuild_gpu_buffers()

                if self.program and self.program.bind():
                    self.program.setUniformValue("u_mvp", self.make_mvp())
                    self.gl.glEnable(self.GL_DEPTH_TEST)

                    if self.triangle_vertex_count > 0:
                        self.vbo_tri.bind()
                        self.configure_attributes(self.vbo_tri)
                        self.gl.glDrawArrays(self.GL_TRIANGLES, 0, self.triangle_vertex_count)
                        self.vbo_tri.release()

                    if self.line_vertex_count > 0:
                        self.vbo_lines.bind()
                        self.configure_attributes(self.vbo_lines)
                        # Небольшой риск z-fighting допустим: линии нужны только как визуальный контур.
                        self.gl.glDrawArrays(self.GL_LINES, 0, self.line_vertex_count)
                        self.vbo_lines.release()

                    self.program.disableAttributeArray(0)
                    self.program.disableAttributeArray(1)
                    self.program.release()
        finally:
            painter.endNativePainting()

        self.draw_overlay_text(painter)
        painter.end()

    def paintEvent(self, event):
        # Если QOpenGLWidget недоступен, показываем сообщение вместо падения GUI.
        if OPENGL_PREVIEW_AVAILABLE:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg)
        self.draw_background_grid(painter)
        painter.setPen(QPen(QColor(230, 230, 230), 1))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "OpenGL-предпросмотр недоступен\nУстанови PySide6 с модулем QtOpenGLWidgets")

    def draw_overlay_text(self, painter: QPainter):
        if not self.mesh.faces:
            painter.setPen(QPen(QColor(210, 210, 210), 1))
            msg = self.mesh.message or "Нет данных для предпросмотра"
            stats = self.mesh.stats or "Выбери .obj файл или нажми «Обновить»"
            if self.gpu_error:
                stats = self.gpu_error
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg + "\n" + stats)
            return

        painter.setPen(QPen(QColor(230, 230, 230), 1))
        painter.drawText(10, 18, self.mesh.message)
        painter.setPen(QPen(QColor(170, 170, 170), 1))
        extra = " | GPU/OpenGL"
        painter.drawText(10, 36, self.mesh.stats + extra)
        painter.setPen(QPen(QColor(120, 120, 120), 1))
        if self.auto_rotate:
            hint = "ЛКМ — вращать, колесо — масштаб, ПКМ — остановить автоповорот, Ctrl+ПКМ — сброс камеры. Предпросмотр рендерится на GPU."
        else:
            hint = "ЛКМ — вращать, колесо — масштаб, ПКМ — автоповорот, Ctrl+ПКМ — сброс камеры. Предпросмотр рендерится на GPU."
        painter.drawText(10, self.height() - 12, hint)

    def draw_background_grid(self, painter: QPainter):
        painter.setPen(self.grid_pen)
        step = int(max(12, min(128, 64 * self.zoom)))
        w = self.width()
        h = self.height()
        ox = int((w * 0.5 + self.pan_x) % step)
        oy = int((h * 0.5 + self.pan_y) % step)
        for x in range(ox, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(oy, h, step):
            painter.drawLine(0, y, w, y)
        painter.setPen(QPen(QColor(65, 65, 65), 1))
        painter.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_dir = get_application_dir()
        self.config_path = self.app_dir / CONFIG_NAME
        self.script_brushes = find_converter_script("obj_to_vmf_brushes.py", self.app_dir)
        self.script_triangles = find_converter_script("obj_to_vmf_triangles.py", self.app_dir)
        self.process = None
        self.aborted_by_user = False
        self.preview_kind = "source"
        self.preview_update_scheduled = False
        # Кэш предпросмотра: при переключении "Исходная модель" <-> "Конвертация"
        # больше не запускаем повторный парсинг OBJ/временную VMF-конвертацию, если
        # файл и параметры не изменились. Это убирает зависания на больших моделях.
        self.preview_cache: Dict[Tuple, PreviewMesh] = {}
        self.preview_cache_order: List[Tuple] = []
        self.preview_cache_limit = 8

        self.setWindowTitle("Сборка VMF - Конвертер моделей Hammer")
        self.resize(1360, 820)
        self.setMinimumSize(1060, 640)
        self.setStyleSheet(STYLE)
        self.apply_palette()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.rebuild_preview)

        # Без AnimatedDocks: перетаскивание dock-разделов остаётся, но без анимаций.
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )

        center = QFrame()
        center.setObjectName("RightPanel")
        center.setMinimumSize(1, 1)
        self.setCentralWidget(center)

        self.settings_dock = self.make_dock("Настройки", self.make_left_panel(), "SettingsDock")
        self.preview_dock = self.make_dock("Предпросмотр", self.make_preview_panel(), "PreviewDock")
        self.output_dock = self.make_dock("Output конвертера", self.make_log_panel(), "OutputDock")

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.settings_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.preview_dock)
        self.splitDockWidget(self.preview_dock, self.output_dock, Qt.Orientation.Vertical)

        self.resizeDocks([self.settings_dock, self.preview_dock], [500, 900], Qt.Orientation.Horizontal)
        self.resizeDocks([self.preview_dock, self.output_dock], [560, 180], Qt.Orientation.Vertical)

        self.make_status_bar()

        self.load_config(silent=True)
        self.update_mode_visibility()
        self.connect_preview_signals()
        self.set_status("Готово", "idle")
        self.schedule_preview_update()

    def apply_palette(self):
        p = QPalette()
        p.setColor(QPalette.ColorRole.Window, QColor("#2f2f2f"))
        p.setColor(QPalette.ColorRole.WindowText, QColor("#cfcfcf"))
        p.setColor(QPalette.ColorRole.Base, QColor("#000000"))
        p.setColor(QPalette.ColorRole.Text, QColor("#e8e8e8"))
        QApplication.instance().setPalette(p)

    def make_dock(self, title, widget, object_name):
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        return dock

    def make_left_panel(self):
        panel = QFrame()
        panel.setObjectName("LeftPanel")
        panel.setMinimumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(6)

        settings_caption = QLabel("Настройки")
        settings_caption.setObjectName("PanelCaption")
        settings_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(settings_caption)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        self.settings_layout = QVBoxLayout(page)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setSpacing(6)
        self.create_sections()
        self.settings_layout.addStretch(1)
        scroll.setWidget(page)
        layout.addWidget(scroll, 1)

        layout.addWidget(self.make_command_buttons())
        return panel

    def make_preview_panel(self):
        panel = QFrame()
        panel.setObjectName("RightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        toolbar = QFrame()
        toolbar.setObjectName("PreviewToolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(6, 4, 6, 4)
        tb.setSpacing(6)

        self.source_preview_btn = QPushButton("Исходная модель")
        self.converted_preview_btn = QPushButton("Конвертация")
        self.gray_btn = QPushButton("Серый")
        self.brush_colors_btn = QPushButton("Цвета брашей")
        self.preview_refresh_btn = QPushButton("Обновить")

        for b in [self.source_preview_btn, self.converted_preview_btn, self.gray_btn, self.brush_colors_btn]:
            b.setCheckable(True)

        self.preview_group = QButtonGroup(self)
        self.preview_group.setExclusive(True)
        self.preview_group.addButton(self.source_preview_btn)
        self.preview_group.addButton(self.converted_preview_btn)
        self.source_preview_btn.setChecked(True)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.color_group.addButton(self.gray_btn)
        self.color_group.addButton(self.brush_colors_btn)
        self.gray_btn.setChecked(True)

        self.source_preview_btn.clicked.connect(lambda: self.set_preview_kind("source"))
        self.converted_preview_btn.clicked.connect(lambda: self.set_preview_kind("converted"))
        self.gray_btn.clicked.connect(lambda: self.preview.set_color_mode("gray"))
        self.brush_colors_btn.clicked.connect(lambda: self.preview.set_color_mode("brushes"))
        self.preview_refresh_btn.clicked.connect(self.force_rebuild_preview)

        tb.addWidget(self.source_preview_btn)
        tb.addWidget(self.converted_preview_btn)
        tb.addSpacing(12)
        tb.addWidget(self.gray_btn)
        tb.addWidget(self.brush_colors_btn)
        tb.addStretch(1)
        tb.addWidget(self.preview_refresh_btn)
        layout.addWidget(toolbar)

        self.preview = PreviewWidget()
        layout.addWidget(self.preview, 1)
        return panel

    def make_log_panel(self):
        panel = QFrame()
        panel.setObjectName("RightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log.setMinimumHeight(80)
        layout.addWidget(self.log, 1)
        return panel

    def make_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color:#ffffff;font-size:8pt; padding-left:6px;")
        self.status_bar.addWidget(self.status_label, 1)
        self.setStatusBar(self.status_bar)
        return self.status_bar

    def make_command_buttons(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        cap = QLabel("Команды")
        cap.setObjectName("PanelCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(cap)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.run_btn = QPushButton("Конвертировать")
        self.run_btn.setObjectName("BuildButton")
        self.copy_btn = QPushButton("Копировать")
        self.stop_btn = QPushButton("Прервать")
        self.stop_btn.setObjectName("AbortButton")
        self.clear_btn = QPushButton("Очистить")
        for b in [self.run_btn, self.copy_btn, self.stop_btn, self.clear_btn]:
            b.setMinimumWidth(92)
            row.addWidget(b)
        layout.addLayout(row)

        self.run_btn.clicked.connect(self.run_converter)
        self.copy_btn.clicked.connect(self.copy_command)
        self.stop_btn.clicked.connect(self.stop_converter)
        self.clear_btn.clicked.connect(lambda: self.log.clear())
        self.stop_btn.setEnabled(False)
        return box

    def create_sections(self):
        self.create_world_section()
        self.create_mode_section()
        self.create_common_section()
        self.create_brush_section()
        self.create_triangle_section()
        self.create_config_section()

    def create_world_section(self):
        s = Section("Входные и выходные файлы")
        self.input_edit = DropLineEdit()
        self.output_folder_edit = QLineEdit()
        self.output_name_edit = QLineEdit("converted.vmf")

        input_btn = QPushButton("...")
        input_btn.setFixedWidth(34)
        output_btn = QPushButton("...")
        output_btn.setFixedWidth(34)
        open_btn = QPushButton("откр.")
        open_btn.setFixedWidth(48)
        input_btn.clicked.connect(self.pick_input)
        output_btn.clicked.connect(self.pick_output_folder)
        open_btn.clicked.connect(self.open_output_folder)

        s.add_row("Входной .obj", self.input_edit, input_btn)
        s.add_row("Папка вывода", self.output_folder_edit, output_btn)
        s.add_row("Имя VMF", self.output_name_edit, open_btn)
        self.settings_layout.addWidget(s)

    def create_mode_section(self):
        s = Section("Режим конвертации")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Выпуклые формы — браши", "brushes")
        self.mode_combo.addItem("1 треугольник = 1 браш", "triangles")
        self.mode_combo.currentIndexChanged.connect(self.update_mode_visibility)
        s.add_row("Режим", self.mode_combo)
        self.settings_layout.addWidget(s)

    def create_common_section(self):
        s = Section("Общие параметры")
        self.scale = self.make_double(0.001, 1000000.0, 4, 1.0)
        self.grid = self.make_double(0.0, 4096.0, 4, 1.0)
        self.axis = QComboBox()
        self.axis.addItems(["xzy", "xyz", "unreal"])
        self.material = QLineEdit("TOOLS/TOOLSNODRAW")
        self.min_area = self.make_double(0.0, 1000000.0, 4, 1.0)
        self.tex_scale = self.make_double(0.001, 1024.0, 4, 0.25)
        s.add_row("--scale", self.scale)
        s.add_row("--grid", self.grid)
        s.add_row("--axis", self.axis)
        s.add_row("--material", self.material)
        s.add_row("--min-area", self.min_area)
        s.add_row("--tex-scale", self.tex_scale)
        self.settings_layout.addWidget(s)

    def create_brush_section(self):
        self.brush_section = Section("Параметры брашей")
        self.brushes_group_by = QComboBox()
        self.brushes_group_by.addItems(["object", "group"])
        self.brushes_max_faces = QSpinBox()
        self.brushes_max_faces.setRange(4, 8192)
        self.brushes_max_faces.setValue(128)
        self.brush_section.add_row("--group-by", self.brushes_group_by)
        self.brush_section.add_row("--max-faces", self.brushes_max_faces)
        self.settings_layout.addWidget(self.brush_section)

    def create_triangle_section(self):
        self.triangle_section = Section("Параметры треугольников")
        self.tri_thickness = self.make_double(0.001, 1024.0, 4, 4.0)
        self.tri_mode = QComboBox()
        self.tri_mode.addItems(["func_illusionary", "func_detail", "world"])
        self.tri_skyname = QLineEdit("painted")
        self.tri_alpha = QSpinBox()
        self.tri_alpha.setRange(0, 255)
        self.tri_alpha.setValue(160)
        self.tri_normal_tolerance = self.make_double(0.0, 90.0, 3, 2.0)
        self.tri_rect_tolerance = self.make_double(0.0, 90.0, 3, 8.0)
        self.tri_no_merge = QCheckBox("--no-merge-triangles")
        self.tri_rect_only = QCheckBox("--rect-only")
        self.triangle_section.add_row("--thickness", self.tri_thickness)
        self.triangle_section.add_row("--mode", self.tri_mode)
        self.triangle_section.add_row("--skyname", self.tri_skyname)
        self.triangle_section.add_row("--alpha", self.tri_alpha)
        self.triangle_section.add_row("--normal-tolerance", self.tri_normal_tolerance)
        self.triangle_section.add_row("--rect-tolerance", self.tri_rect_tolerance)
        self.triangle_section.add_full(self.tri_no_merge)
        self.triangle_section.add_full(self.tri_rect_only)
        self.settings_layout.addWidget(self.triangle_section)

    def create_config_section(self):
        s = Section("Конфигурация")
        row = QWidget()
        l = QHBoxLayout(row)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(4)
        self.save_cfg_btn = QPushButton("Сохранить")
        self.load_cfg_btn = QPushButton("Загрузить")
        self.reset_cfg_btn = QPushButton("Сбросить")
        l.addWidget(self.save_cfg_btn)
        l.addWidget(self.load_cfg_btn)
        l.addWidget(self.reset_cfg_btn)
        s.add_full(row)
        self.save_cfg_btn.clicked.connect(self.save_config_clicked)
        self.load_cfg_btn.clicked.connect(self.load_config_clicked)
        self.reset_cfg_btn.clicked.connect(self.reset_config)
        self.settings_layout.addWidget(s)

    def make_double(self, min_v, max_v, decimals, value):
        w = QDoubleSpinBox()
        w.setRange(min_v, max_v)
        w.setDecimals(decimals)
        w.setValue(value)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return w

    def connect_preview_signals(self):
        widgets = [
            self.input_edit, self.mode_combo, self.scale, self.grid, self.axis,
            self.min_area, self.brushes_group_by, self.brushes_max_faces,
            self.tri_thickness, self.tri_no_merge, self.tri_rect_only,
            self.tri_normal_tolerance, self.tri_rect_tolerance,
        ]
        self.input_edit.textChanged.connect(self.schedule_preview_update)
        self.mode_combo.currentIndexChanged.connect(self.schedule_preview_update)
        self.scale.valueChanged.connect(self.schedule_preview_update)
        self.grid.valueChanged.connect(self.schedule_preview_update)
        self.axis.currentIndexChanged.connect(self.schedule_preview_update)
        self.min_area.valueChanged.connect(self.schedule_preview_update)
        self.brushes_group_by.currentIndexChanged.connect(self.schedule_preview_update)
        self.brushes_max_faces.valueChanged.connect(self.schedule_preview_update)
        self.tri_thickness.valueChanged.connect(self.schedule_preview_update)
        self.tri_no_merge.stateChanged.connect(self.schedule_preview_update)
        self.tri_rect_only.stateChanged.connect(self.schedule_preview_update)
        self.tri_normal_tolerance.valueChanged.connect(self.schedule_preview_update)
        self.tri_rect_tolerance.valueChanged.connect(self.schedule_preview_update)

    def file_signature(self, path: Path):
        try:
            st = path.stat()
            return (str(path.resolve()).lower(), int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (str(path).lower(), 0, 0)

    def script_signature(self, path: Path):
        try:
            st = path.stat()
            return (str(path.resolve()).lower(), int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (str(path).lower(), 0, 0)

    def current_preview_cache_key(self, kind: Optional[str] = None):
        kind = kind or self.preview_kind
        input_path = Path(self.input_edit.text().strip())
        if not input_path.exists() or input_path.suffix.lower() != ".obj":
            return None

        source_sig = self.file_signature(input_path)
        axis = self.axis.currentText()

        if kind == "source":
            return ("source", source_sig, axis)

        mode = self.mode_combo.currentData()
        script = self.script_brushes if mode == "brushes" else self.script_triangles
        base = (
            "converted",
            source_sig,
            self.script_signature(script),
            mode,
            round(float(self.scale.value()), 6),
            round(float(self.grid.value()), 6),
            axis,
            self.material.text().strip() or "TOOLS/TOOLSNODRAW",
            round(float(self.min_area.value()), 6),
            round(float(self.tex_scale.value()), 6),
        )
        if mode == "brushes":
            return base + (
                self.brushes_group_by.currentText(),
                int(self.brushes_max_faces.value()),
            )
        return base + (
            round(float(self.tri_thickness.value()), 6),
            self.tri_mode.currentText(),
            self.tri_skyname.text().strip() or "painted",
            int(self.tri_alpha.value()),
            bool(self.tri_no_merge.isChecked()),
            round(float(self.tri_normal_tolerance.value()), 6),
            bool(self.tri_rect_only.isChecked()),
            round(float(self.tri_rect_tolerance.value()), 6),
        )

    def get_cached_preview(self, key):
        if key is None:
            return None
        mesh = self.preview_cache.get(key)
        if mesh is not None:
            # LRU-порядок: недавно использованное — в конец.
            try:
                self.preview_cache_order.remove(key)
            except ValueError:
                pass
            self.preview_cache_order.append(key)
        return mesh

    def put_cached_preview(self, key, mesh: PreviewMesh):
        if key is None or mesh is None:
            return
        self.preview_cache[key] = mesh
        try:
            self.preview_cache_order.remove(key)
        except ValueError:
            pass
        self.preview_cache_order.append(key)
        while len(self.preview_cache_order) > self.preview_cache_limit:
            old_key = self.preview_cache_order.pop(0)
            self.preview_cache.pop(old_key, None)

    def clear_preview_cache(self):
        self.preview_cache.clear()
        self.preview_cache_order.clear()

    def set_preview_kind(self, kind: str):
        self.preview_kind = kind
        key = self.current_preview_cache_key(kind)
        cached = self.get_cached_preview(key)
        if cached is not None:
            self.preview.set_mesh(cached)
            return
        self.schedule_preview_update(delay=0)

    def schedule_preview_update(self, *args, delay: int = 650):
        if hasattr(self, "preview_timer"):
            # Треугольный режим тяжелее, поэтому обновляем его чуть реже.
            if hasattr(self, "mode_combo") and self.mode_combo.currentData() == "triangles":
                delay = max(delay, 1400)
            self.preview_timer.start(delay)

    def force_rebuild_preview(self):
        key = self.current_preview_cache_key(self.preview_kind)
        if key is not None:
            self.preview_cache.pop(key, None)
            try:
                self.preview_cache_order.remove(key)
            except ValueError:
                pass
        self.rebuild_preview()

    def rebuild_preview(self):
        cache_key = None
        try:
            input_path = Path(self.input_edit.text().strip())
            if not input_path.exists() or input_path.suffix.lower() != ".obj":
                mesh = PreviewMesh()
                mesh.message = "Нет OBJ-файла"
                mesh.stats = "Выбери входной .obj для предпросмотра"
                self.preview.set_mesh(mesh)
                return

            cache_key = self.current_preview_cache_key(self.preview_kind)
            cached = self.get_cached_preview(cache_key)
            if cached is not None:
                self.preview.set_mesh(cached)
                return

            if self.preview_kind == "source":
                # Исходная модель нужна как эталон. Поэтому параметр --scale
                # здесь намеренно не применяется: размер меняется только во
                # вкладке «Конвертация». Grid также отключён, чтобы исходник
                # не искажался настройками сборки.
                mesh = build_source_preview(
                    str(input_path), 1.0, 0.0, self.axis.currentText()
                )
                apply_reference_view_size(mesh, str(input_path), self.axis.currentText())
            else:
                mode = self.mode_combo.currentData()
                script = self.script_brushes if mode == "brushes" else self.script_triangles
                if script.exists():
                    mesh = build_real_converted_preview(
                        str(script), str(input_path), mode,
                        self.scale.value(), self.grid.value(), self.axis.currentText(),
                        self.material.text().strip() or "TOOLS/TOOLSNODRAW",
                        self.min_area.value(), self.tex_scale.value(),
                        self.brushes_group_by.currentText(), self.brushes_max_faces.value(),
                        self.tri_thickness.value(), self.tri_mode.currentText(),
                        self.tri_skyname.text().strip() or "painted", self.tri_alpha.value(),
                        self.tri_no_merge.isChecked(), self.tri_normal_tolerance.value(),
                        self.tri_rect_only.isChecked(), self.tri_rect_tolerance.value()
                    )
                    # Если реальный VMF создался, но его нельзя пересобрать в полигональный
                    # предпросмотр, не оставляем пустое окно: строим быстрый внутренний
                    # предпросмотр по той же логике. Это не замена финальной VMF-сборки,
                    # а страховка для нестандартных/сложных solid-блоков.
                    if not mesh.faces:
                        if mode == "brushes":
                            mesh = build_brush_preview(
                                str(input_path), self.scale.value(), self.grid.value(), self.axis.currentText(),
                                self.brushes_group_by.currentText(), self.min_area.value(), self.brushes_max_faces.value()
                            )
                            mesh.message = "Предпросмотр: выпуклые формы — браши (быстрый fallback)"
                        else:
                            mesh = build_triangle_preview(
                                str(input_path), self.scale.value(), self.grid.value(), self.axis.currentText(),
                                self.min_area.value(), self.tri_thickness.value(), self.tri_no_merge.isChecked(),
                                self.tri_normal_tolerance.value(), self.tri_rect_only.isChecked(), self.tri_rect_tolerance.value()
                            )
                            mesh.message = "Предпросмотр: 1 треугольник = 1 браш (быстрый fallback)"
                elif mode == "brushes":
                    mesh = build_brush_preview(
                        str(input_path), self.scale.value(), self.grid.value(), self.axis.currentText(),
                        self.brushes_group_by.currentText(), self.min_area.value(), self.brushes_max_faces.value()
                    )
                else:
                    mesh = build_triangle_preview(
                        str(input_path), self.scale.value(), self.grid.value(), self.axis.currentText(),
                        self.min_area.value(), self.tri_thickness.value(), self.tri_no_merge.isChecked(),
                        self.tri_normal_tolerance.value(), self.tri_rect_only.isChecked(), self.tri_rect_tolerance.value()
                    )
            apply_reference_view_size(mesh, str(input_path), self.axis.currentText())
            self.put_cached_preview(cache_key, mesh)
            self.preview.set_mesh(mesh)
        except Exception as e:
            mesh = PreviewMesh()
            mesh.message = "Ошибка предпросмотра"
            mesh.stats = str(e)
            self.preview.set_mesh(mesh)

    def default_config(self):
        return {
            "input_path": "",
            "output_folder": "",
            "output_name": "converted.vmf",
            "mode": "brushes",
            "scale": 1.0,
            "grid": 1.0,
            "axis": "xzy",
            "material": "TOOLS/TOOLSNODRAW",
            "min_area": 1.0,
            "tex_scale": 0.25,
            "brushes_group_by": "object",
            "brushes_max_faces": 128,
            "tri_thickness": 4.0,
            "tri_mode": "func_illusionary",
            "tri_skyname": "painted",
            "tri_alpha": 160,
            "tri_no_merge": False,
            "tri_rect_only": False,
            "tri_normal_tolerance": 2.0,
            "tri_rect_tolerance": 8.0,
        }

    def collect_config(self):
        return {
            "input_path": self.input_edit.text(),
            "output_folder": self.output_folder_edit.text(),
            "output_name": self.output_name_edit.text(),
            "mode": self.mode_combo.currentData(),
            "scale": self.scale.value(),
            "grid": self.grid.value(),
            "axis": self.axis.currentText(),
            "material": self.material.text(),
            "min_area": self.min_area.value(),
            "tex_scale": self.tex_scale.value(),
            "brushes_group_by": self.brushes_group_by.currentText(),
            "brushes_max_faces": self.brushes_max_faces.value(),
            "tri_thickness": self.tri_thickness.value(),
            "tri_mode": self.tri_mode.currentText(),
            "tri_skyname": self.tri_skyname.text(),
            "tri_alpha": self.tri_alpha.value(),
            "tri_no_merge": self.tri_no_merge.isChecked(),
            "tri_rect_only": self.tri_rect_only.isChecked(),
            "tri_normal_tolerance": self.tri_normal_tolerance.value(),
            "tri_rect_tolerance": self.tri_rect_tolerance.value(),
        }

    def apply_config(self, cfg):
        d = self.default_config()
        d.update(cfg or {})
        cfg = d
        self.input_edit.setText(str(cfg["input_path"]))
        self.output_folder_edit.setText(str(cfg["output_folder"]))
        self.output_name_edit.setText(str(cfg["output_name"]))
        self.set_combo_by_data(self.mode_combo, cfg["mode"])
        self.scale.setValue(float(cfg["scale"]))
        self.grid.setValue(float(cfg["grid"]))
        self.set_combo_by_text(self.axis, cfg["axis"])
        self.material.setText(str(cfg["material"]))
        self.min_area.setValue(float(cfg["min_area"]))
        self.tex_scale.setValue(float(cfg["tex_scale"]))
        self.set_combo_by_text(self.brushes_group_by, cfg["brushes_group_by"])
        self.brushes_max_faces.setValue(int(cfg["brushes_max_faces"]))
        self.tri_thickness.setValue(float(cfg["tri_thickness"]))
        self.set_combo_by_text(self.tri_mode, cfg["tri_mode"])
        self.tri_skyname.setText(str(cfg["tri_skyname"]))
        self.tri_alpha.setValue(int(cfg["tri_alpha"]))
        self.tri_no_merge.setChecked(bool(cfg["tri_no_merge"]))
        self.tri_rect_only.setChecked(bool(cfg["tri_rect_only"]))
        self.tri_normal_tolerance.setValue(float(cfg["tri_normal_tolerance"]))
        self.tri_rect_tolerance.setValue(float(cfg["tri_rect_tolerance"]))

    def save_config(self):
        self.config_path.write_text(
            json.dumps(self.collect_config(), indent=4, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_config(self, silent=False):
        if not self.config_path.exists():
            self.apply_config(self.default_config())
            if not silent:
                self.append_log("Конфиг не найден. Загружены настройки по умолчанию.\n")
            return
        try:
            self.apply_config(json.loads(self.config_path.read_text(encoding="utf-8")))
            if not silent:
                self.append_log(f"Конфиг загружен: {self.config_path}\n")
        except Exception as e:
            self.apply_config(self.default_config())
            if not silent:
                QMessageBox.warning(self, "Ошибка конфига", f"Не удалось прочитать конфиг:\n{e}")

    def save_config_clicked(self):
        try:
            self.save_config()
            self.append_log(f"Конфиг сохранён: {self.config_path}\n")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить конфиг:\n{e}")

    def load_config_clicked(self):
        self.load_config(silent=False)
        self.update_mode_visibility()
        self.schedule_preview_update()

    def reset_config(self):
        self.apply_config(self.default_config())
        self.save_config()
        self.update_mode_visibility()
        self.schedule_preview_update()
        self.append_log("Конфиг сброшен.\n")

    def closeEvent(self, event):
        try:
            self.save_config()
        except Exception:
            pass
        super().closeEvent(event)

    def set_combo_by_text(self, combo, text):
        idx = combo.findText(str(text))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def set_combo_by_data(self, combo, data):
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    def pick_input(self):
        start = self.input_edit.text().strip()
        start_dir = str(Path(start).parent) if start else ""
        p, _ = QFileDialog.getOpenFileName(self, "Выбери OBJ", start_dir, "OBJ files (*.obj);;All files (*.*)")
        if p:
            self.input_edit.setText(p)
            if not self.output_folder_edit.text().strip():
                self.output_folder_edit.setText(str(Path(p).parent))
            if self.output_name_edit.text().strip() == "converted.vmf":
                self.output_name_edit.setText(Path(p).stem + ".vmf")
            self.save_config()
            self.schedule_preview_update(delay=0)

    def pick_output_folder(self):
        start = self.output_folder_edit.text().strip()
        p = QFileDialog.getExistingDirectory(self, "Выбери папку вывода", start)
        if p:
            self.output_folder_edit.setText(p)
            self.save_config()

    def open_output_folder(self):
        folder = self.output_folder_edit.text().strip()
        if not folder:
            return
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            import os
            os.startfile(str(p))
        else:
            QMessageBox.information(self, "Папка вывода", str(p))

    def update_mode_visibility(self):
        is_brushes = self.mode_combo.currentData() == "brushes"
        for w in [self.brushes_group_by, self.brushes_max_faces]:
            w.setEnabled(is_brushes)
        for w in [
            self.tri_thickness, self.tri_mode, self.tri_skyname, self.tri_alpha,
            self.tri_no_merge, self.tri_rect_only,
            self.tri_normal_tolerance, self.tri_rect_tolerance,
        ]:
            w.setEnabled(not is_brushes)
        if hasattr(self, "preview_kind") and self.preview_kind == "converted":
            self.schedule_preview_update()

    def output_path(self):
        folder = Path(self.output_folder_edit.text().strip())
        name = self.output_name_edit.text().strip()
        if not name.lower().endswith(".vmf"):
            name += ".vmf"
        return folder / name

    def validate(self):
        input_path = Path(self.input_edit.text().strip())
        output_folder = Path(self.output_folder_edit.text().strip())
        output_name = self.output_name_edit.text().strip()
        if not input_path.exists():
            raise ValueError("Входной .obj файл не найден.")
        if input_path.suffix.lower() != ".obj":
            raise ValueError("Входной файл должен иметь расширение .obj.")
        if not str(output_folder):
            raise ValueError("Папка вывода не указана.")
        if not output_name:
            raise ValueError("Имя выходного VMF не указано.")
        output_folder.mkdir(parents=True, exist_ok=True)
        mode = self.mode_combo.currentData()
        script = self.script_brushes if mode == "brushes" else self.script_triangles
        if not script.exists():
            raise ValueError(
                "Скрипт конвертера не найден:\n"
                f"{script}\n\n"
                "Положи obj_to_vmf_brushes.py и obj_to_vmf_triangles.py рядом с EXE "
                "или в папку _internal рядом с EXE.\n\n"
                f"Текущая папка программы: {self.app_dir}"
            )
        return input_path, self.output_path(), script, mode

    def build_command(self):
        input_path, output_path, script, mode = self.validate()
        if is_frozen_app():
            args = [
                sys.executable,
                "--run-converter-script",
                str(script),
                str(input_path),
                str(output_path),
            ]
        else:
            args = [
                sys.executable,
                str(script),
                str(input_path),
                str(output_path),
            ]

        args += [
            "--scale", str(self.scale.value()),
            "--grid", str(self.grid.value()),
            "--axis", self.axis.currentText(),
            "--material", self.material.text().strip() or "TOOLS/TOOLSNODRAW",
            "--min-area", str(self.min_area.value()),
            "--tex-scale", str(self.tex_scale.value()),
        ]
        if mode == "brushes":
            args += [
                "--group-by", self.brushes_group_by.currentText(),
                "--max-faces", str(self.brushes_max_faces.value()),
            ]
        else:
            args += [
                "--thickness", str(self.tri_thickness.value()),
                "--mode", self.tri_mode.currentText(),
                "--skyname", self.tri_skyname.text().strip() or "painted",
                "--alpha", str(self.tri_alpha.value()),
                "--normal-tolerance", str(self.tri_normal_tolerance.value()),
                "--rect-tolerance", str(self.tri_rect_tolerance.value()),
            ]
            if self.tri_no_merge.isChecked():
                args.append("--no-merge-triangles")
            if self.tri_rect_only.isChecked():
                args.append("--rect-only")
        return args

    def command_as_text(self, args):
        if sys.platform.startswith("win"):
            return windows_cmdline(args)
        return " ".join(shlex.quote(a) for a in args)

    def copy_command(self):
        try:
            args = self.build_command()
            QApplication.clipboard().setText(self.command_as_text(args))
            self.append_log("Команда скопирована в буфер обмена.\n")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def run_converter(self):
        try:
            self.save_config()
            args = self.build_command()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        if self.process is not None:
            QMessageBox.warning(self, "Уже запущено", "Конвертер уже работает.")
            return

        self.aborted_by_user = False
        self.log.clear()
        self.append_log("Запуск конвертации: " + self.output_name_edit.text().strip() + "\n")
        self.append_log("Конвертер моделей Hammer инициализирован.\n")
        self.append_log("Командная строка:\n" + self.command_as_text(args) + "\n\n")

        self.process = QProcess(self)
        self.process.setProgram(args[0])
        self.process.setArguments(args[1:])
        script_arg_index = 2 if is_frozen_app() else 1
        self.process.setWorkingDirectory(str(Path(args[script_arg_index]).resolve().parent))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.process_finished)

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.set_status("Выполняется", "running")
        self.process.start()
        if not self.process.waitForStarted(3000):
            self.append_log("ОШИБКА: процесс не запустился.\n")
            self.process_finished(-1, QProcess.ExitStatus.CrashExit)

    def stop_converter(self):
        if self.process:
            self.aborted_by_user = True
            self.process.kill()
            self.append_log("\nЗапрошено прерывание.\n")
            self.set_status("Прервано", "error")

    def read_stdout(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.append_log(data)

    def read_stderr(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self.append_log(data)

    def process_finished(self, exit_code, exit_status):
        self.append_log(f"\nFINISHED: exit_code={exit_code}, status={exit_status}\n")
        self.process = None
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.aborted_by_user:
            self.set_status("Прервано", "error")
        elif exit_code == 0:
            self.set_status("Готово", "ok")
        else:
            self.set_status("Ошибка", "error")

    def set_status(self, text, mode):
        self.status_label.setText(text)
        if mode == "ok":
            self.status_bar.setStyleSheet("QStatusBar { background:#21702e; color:#ffffff; border-top:1px solid #0f3f18; }")
        elif mode == "running":
            self.status_bar.setStyleSheet("QStatusBar { background:#9a5a14; color:#ffffff; border-top:1px solid #5c3308; }")
        elif mode == "idle":
            self.status_bar.setStyleSheet("QStatusBar { background:#3a3a3a; color:#ffffff; border-top:1px solid #1f1f1f; }")
        else:
            self.status_bar.setStyleSheet("QStatusBar { background:#aa1414; color:#ffffff; border-top:1px solid #5b0000; }")

    def append_log(self, text):
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)


def is_frozen_app():
    return bool(getattr(sys, "frozen", False))


def get_application_dir():
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_converter_script(filename, app_dir):
    candidates = [
        app_dir / filename,
        app_dir / "_internal" / filename,
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / filename)
        candidates.append(Path(meipass) / "_internal" / filename)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return app_dir / filename


def run_converter_script_from_exe():
    if len(sys.argv) < 3 or sys.argv[1] != "--run-converter-script":
        return False
    script = Path(sys.argv[2]).resolve()
    if not script.exists():
        print(f"ERROR: converter script not found: {script}", file=sys.stderr)
        return True
    sys.argv = [str(script)] + sys.argv[3:]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        raise e
    except Exception as e:
        print(f"ERROR: converter script crashed: {e}", file=sys.stderr)
        raise
    return True


def windows_cmdline(seq):
    result = []
    for arg in seq:
        arg = str(arg)
        bs_buf = []
        needquote = (" " in arg) or ("\t" in arg) or not arg
        if needquote:
            result.append('"')
        for c in arg:
            if c == "\\":
                bs_buf.append(c)
            elif c == '"':
                result.append("".join(bs_buf * 2))
                bs_buf = []
                result.append('\\"')
            else:
                if bs_buf:
                    result.append("".join(bs_buf))
                    bs_buf = []
                result.append(c)
        if bs_buf:
            result.append("".join(bs_buf * 2 if needquote else bs_buf))
        if needquote:
            result.append('"')
        result.append(" ")
    return "".join(result).strip()


def main():
    if run_converter_script_from_exe():
        return
    # OpenGL-предпросмотр: задаём стабильный compatibility profile для Windows/Intel/NVIDIA/AMD.
    try:
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        fmt.setVersion(2, 1)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
