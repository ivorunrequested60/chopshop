from __future__ import annotations

"""
Connector generation utilities.

Defaults (from CLAUDE.md):
- Dovetail connectors as default joint type.
- 0.2mm clearance on female joints for FDM tolerances.
"""

from dataclasses import dataclass
from typing import Literal, Tuple

import numpy as np
import trimesh


DEFAULT_CLEARANCE_MM = 0.2
CONNECTOR_SPACING_MM = 30.0
CONNECTOR_EDGE_INSET_MM = 10.0
MIN_MATERIAL_THICKNESS_MM = 5.0


@dataclass
class DovetailSpec:
    """
    Geometric specification for a dovetail connector.

    The dovetail is modeled as a 2D trapezoid extruded along +Z. In local
    coordinates the base lies in the XY plane with z=0 and extends to z=length.
    """

    width_mm: float
    depth_mm: float
    length_mm: float
    clearance_mm: float = DEFAULT_CLEARANCE_MM


def generate_dovetail_male(width: float, depth: float, length: float) -> trimesh.Trimesh:
    """
    Create a simple male dovetail prism as a :class:`trimesh.Trimesh`.

    The local coordinate frame is:
        - Base plane at z = 0.
        - Extrusion direction along +Z with extent ``length``.
        - Dovetail centered at the origin in XY with overall width ``width``
          and depth ``depth``.
    """

    half_w = width / 2.0
    half_d = depth / 2.0

    # Trapezoid in XY: wider at the base, narrower at the tip.
    base_scale = 1.0
    tip_scale = 0.6

    base_vertices = np.array(
        [
            [-half_w * base_scale, -half_d, 0.0],
            [half_w * base_scale, -half_d, 0.0],
            [half_w * base_scale, half_d, 0.0],
            [-half_w * base_scale, half_d, 0.0],
        ],
        dtype=float,
    )
    tip_vertices = np.array(
        [
            [-half_w * tip_scale, -half_d * tip_scale, length],
            [half_w * tip_scale, -half_d * tip_scale, length],
            [half_w * tip_scale, half_d * tip_scale, length],
            [-half_w * tip_scale, half_d * tip_scale, length],
        ],
        dtype=float,
    )

    vertices = np.vstack([base_vertices, tip_vertices])

    # Faces for a prism made of two quads (base and tip) and 4 side quads.
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],  # base
            [4, 6, 5],
            [4, 7, 6],  # tip
            [0, 4, 5],
            [0, 5, 1],  # side 1
            [1, 5, 6],
            [1, 6, 2],  # side 2
            [2, 6, 7],
            [2, 7, 3],  # side 3
            [3, 7, 4],
            [3, 4, 0],  # side 4
        ],
        dtype=int,
    )

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


def generate_dovetail_female(
    width: float,
    depth: float,
    length: float,
    tolerance: float = DEFAULT_CLEARANCE_MM,
) -> trimesh.Trimesh:
    """
    Create a female dovetail cavity shape matching the male connector.

    The cavity is simply a slightly enlarged version of the male geometry so
    that boolean subtraction leaves clearance for FDM printing.
    """

    male = generate_dovetail_male(width, depth, length)

    # Uniform scaling about the origin to provide clearance.
    scale = 1.0 + (tolerance / max(width, depth, length))
    transform = np.eye(4, dtype=float)
    transform[0, 0] = scale
    transform[1, 1] = scale
    transform[2, 2] = scale
    female = male.copy()
    female.apply_transform(transform)
    return female


def _build_face_frame(
    normal: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Construct an orthonormal basis (tangent_u, tangent_v, normal) for a face.
    """

    n = normal / np.linalg.norm(normal)
    # Pick an arbitrary vector not parallel to n.
    if abs(n[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0], dtype=float)
    else:
        ref = np.array([0.0, 1.0, 0.0], dtype=float)
    tangent_u = np.cross(n, ref)
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(n, tangent_u)
    tangent_v /= np.linalg.norm(tangent_v)
    return tangent_u, tangent_v, n


def _compute_face_bounds_on_plane(
    mesh: trimesh.Trimesh,
    point: np.ndarray,
    normal: np.ndarray,
) -> Tuple[float, float, float, float]:
    """
    Approximate the bounds of the mesh intersection with a plane.

    Projects all mesh vertices onto a 2D frame on the plane and returns the
    min/max coordinates along the two in-plane axes.
    """

    tangent_u, tangent_v, n = _build_face_frame(normal)
    # Project vertices into the face coordinate system.
    rel = mesh.vertices - point
    u = rel @ tangent_u
    v = rel @ tangent_v
    return float(u.min()), float(u.max()), float(v.min()), float(v.max())


def _sample_connector_grid(
    u_min: float,
    u_max: float,
    v_min: float,
    v_max: float,
    spacing: float,
    inset: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute grid coordinates (u, v) inside the insets with fixed spacing.
    """

    inner_u_min = u_min + inset
    inner_u_max = u_max - inset
    inner_v_min = v_min + inset
    inner_v_max = v_max - inset

    if inner_u_min >= inner_u_max or inner_v_min >= inner_v_max:
        return np.array([]), np.array([])

    u_vals = np.arange(inner_u_min, inner_u_max + 1e-6, spacing, dtype=float)
    v_vals = np.arange(inner_v_min, inner_v_max + 1e-6, spacing, dtype=float)
    return u_vals, v_vals


def _ray_has_sufficient_material(
    mesh: trimesh.Trimesh,
    origin: np.ndarray,
    direction: np.ndarray,
    min_distance: float,
) -> bool:
    """
    Use ray casting to ensure there is enough material behind a connector.
    """

    direction = direction / np.linalg.norm(direction)
    # Use trimesh's generic ray interface; pyembree is optional.
    r = trimesh.ray.ray_pyembree.RayMeshIntersector(mesh)  # type: ignore[attr-defined]
    locations, _index_ray, _index_tri = r.intersects_location(
        origins=origin.reshape(1, 3),
        directions=direction.reshape(1, 3),
        multiple_hits=False,
    )
    if len(locations) == 0:
        return False
    dist = np.linalg.norm(locations[0] - origin)
    return dist >= min_distance


def place_connectors(
    chunk_mesh: trimesh.Trimesh,
    cut_face_plane: Tuple[np.ndarray, np.ndarray],
    side: Literal["male", "female"] = "male",
    width: float = 8.0,
    depth: float = 4.0,
    length: float = 10.0,
    tolerance: float = DEFAULT_CLEARANCE_MM,
) -> trimesh.Trimesh:
    """
    Place dovetail connectors on a cut face and apply boolean operations.

    Args:
        chunk_mesh: The chunk mesh to modify.
        cut_face_plane: Tuple ``(point, normal)`` describing the cut face.
        side: ``\"male\"`` to union protrusions, ``\"female\"`` to subtract
            cavities.
        width, depth, length: Dovetail dimensions in millimetres.
        tolerance: Clearance for female connectors.
    """

    point, normal = cut_face_plane
    point = np.asarray(point, dtype=float)
    normal = np.asarray(normal, dtype=float)

    tangent_u, tangent_v, n = _build_face_frame(normal)
    u_min, u_max, v_min, v_max = _compute_face_bounds_on_plane(
        chunk_mesh, point, n
    )

    u_vals, v_vals = _sample_connector_grid(
        u_min,
        u_max,
        v_min,
        v_max,
        spacing=CONNECTOR_SPACING_MM,
        inset=CONNECTOR_EDGE_INSET_MM,
    )
    if u_vals.size == 0 or v_vals.size == 0:
        return chunk_mesh

    if side == "male":
        connector_proto = generate_dovetail_male(width, depth, length)
    else:
        connector_proto = generate_dovetail_female(width, depth, length, tolerance)

    connectors: list[trimesh.Trimesh] = []

    for u in u_vals:
        for v in v_vals:
            base_point = point + u * tangent_u + v * tangent_v
            if not _ray_has_sufficient_material(
                chunk_mesh, base_point, -n, MIN_MATERIAL_THICKNESS_MM
            ):
                continue

            # Orient connector so its +Z aligns with the face normal.
            # Build rotation matrix from connector local axes to world axes.
            # Local basis is (x, y, z) = (1, 0, 0), (0, 1, 0), (0, 0, 1).
            rot = np.eye(4, dtype=float)
            rot[0:3, 0] = tangent_u
            rot[0:3, 1] = tangent_v
            rot[0:3, 2] = n

            trans = np.eye(4, dtype=float)
            trans[0:3, 3] = base_point

            transform = trans @ rot

            inst = connector_proto.copy()
            inst.apply_transform(transform)
            connectors.append(inst)

    if not connectors:
        return chunk_mesh

    all_connectors = trimesh.util.concatenate(connectors)

    # Use trimesh boolean operations; if manifold3d-backed booleans are
    # configured, they can be swapped in here later.
    if side == "male":
        result = trimesh.boolean.union([chunk_mesh, all_connectors])
    else:
        result = trimesh.boolean.difference(chunk_mesh, all_connectors)

    if isinstance(result, list):
        # Union may return a list; take the largest component.
        result = max(result, key=lambda m: m.volume)
    return result


if __name__ == "__main__":
    # Simple smoke test: apply connectors to one face of a box.
    box = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    # Choose the +Z face.
    point = np.array([0.0, 0.0, 20.0], dtype=float)
    normal = np.array([0.0, 0.0, 1.0], dtype=float)

    try:
        modified = place_connectors(
            box,
            (point, normal),
            side="male",
            width=8.0,
            depth=4.0,
            length=10.0,
        )
    except Exception as exc:  # pragma: no cover - manual smoke path
        print(f"Connector placement failed: {exc}")
    else:
        Path("output").mkdir(parents=True, exist_ok=True)
        out_path = Path("output") / "connector_test.stl"
        modified.export(out_path)
        print(f"Wrote connector test STL to {out_path}")

