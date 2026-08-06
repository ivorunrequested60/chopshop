from __future__ import annotations

"""
Mesh chunking core logic.

Constraints from global CLAUDE.md:
- Target printer: Bambu Lab A1 Mini (180x180x180mm build volume)
- Use 170x170x170mm as effective max chunk size (10mm margin)
- Dovetail connectors as default joint type
- 0.2mm tolerance on female joints

This module will expose a `chunk_mesh` API that takes a watertight mesh
and returns per-chunk meshes plus connector metadata.
"""

from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import trimesh

try:
    # manifold3d Python bindings are expected to be available in the environment.
    import manifold3d as _manifold  # type: ignore[import]
    from manifold3d import OpType as _OpType  # type: ignore[import]
except ImportError:  # pragma: no cover - runtime environment detail
    _manifold = None  # type: ignore[assignment]
    _OpType = None  # type: ignore[assignment]


MAX_BUILD_CUBE_MM = 170.0


@dataclass
class Chunk:
    """
    Represents a single printable chunk produced by spatial partitioning.

    Attributes:
        chunk_id: Stable identifier in the form ``chunk_i_j_k``.
        mesh: The watertight mesh for this chunk in model coordinates.
        position_in_grid: Integer (i, j, k) indices in the chunk grid.
        cut_faces: List of face direction labels (e.g. ``\"+x\"``, ``\"-y\"``)
            indicating which sides of the chunk correspond to artificial cuts.
        bounding_box: Axis-aligned bounding box as a (2, 3) array
            ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]``.
    """

    chunk_id: str
    mesh: trimesh.Trimesh
    position_in_grid: Tuple[int, int, int]
    cut_faces: List[str]
    bounding_box: np.ndarray


@dataclass
class ChunkMetadata:
    """
    Backwards-compatible metadata container for legacy callers.

    New code should prefer the higher-fidelity :class:`Chunk` objects returned
    by :class:`ChunkEngine`.
    """

    id: str
    transform: np.ndarray
    connector_pairs: List[Tuple[int, int]]


class ChunkEngine:
    """
    Chunking engine that splits a mesh into printable sub-chunks.

    Typical usage::

        engine = ChunkEngine(\"/path/to/model.stl\")
        chunks = engine.run()
    """

    def __init__(
        self,
        stl_path: str,
        max_dimensions: Sequence[float] | None = None,
        output_dir: str | Path = "output",
    ) -> None:
        self.stl_path = Path(stl_path)
        if max_dimensions is None:
            max_dimensions = (MAX_BUILD_CUBE_MM,) * 3
        if len(max_dimensions) != 3:
            raise ValueError("max_dimensions must be a 3-element sequence")
        self.max_dimensions = tuple(float(v) for v in max_dimensions)
        self.output_dir = Path(output_dir)

    def run(self) -> List[Chunk]:
        """
        Execute the full chunking workflow.

        Returns:
            A list of :class:`Chunk` instances and writes each chunk to
            ``output_dir`` as ``chunk_i_j_k.stl``.
        """

        mesh = self._load_and_repair_mesh()
        bounds = mesh.bounds  # (2, 3)
        extents = bounds[1] - bounds[0]

        if np.all(extents <= np.asarray(self.max_dimensions, dtype=float)):
            self.output_dir.mkdir(parents=True, exist_ok=True)
            chunk_id = "chunk_0_0_0"
            output_path = self.output_dir / f"{chunk_id}.stl"
            mesh.export(output_path)
            return [
                Chunk(
                    chunk_id=chunk_id,
                    mesh=mesh,
                    position_in_grid=(0, 0, 0),
                    cut_faces=[],
                    bounding_box=bounds,
                )
            ]

        grid_counts, grid_edges = self._compute_grid(bounds)
        chunks = self._slice_into_chunks(mesh, bounds, grid_counts, grid_edges)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        for chunk in chunks:
            output_path = self.output_dir / f"{chunk.chunk_id}.stl"
            chunk.mesh.export(output_path)

        return chunks

    def _load_and_repair_mesh(self) -> trimesh.Trimesh:
        if not self.stl_path.is_file():
            raise FileNotFoundError(f"STL file not found: {self.stl_path}")

        mesh = trimesh.load_mesh(self.stl_path, file_type="stl")
        if not isinstance(mesh, trimesh.Trimesh):
            mesh = mesh.dump().sum()  # type: ignore[assignment]

        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fill_holes(mesh)
        return mesh

    def _compute_grid(
        self, bounds: np.ndarray
    ) -> Tuple[Tuple[int, int, int], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        mins, maxs = bounds
        extents = maxs - mins
        max_dims = np.asarray(self.max_dimensions, dtype=float)

        counts = [max(1, int(ceil(extents[i] / max_dims[i]))) for i in range(3)]
        edges = []
        for i in range(3):
            if counts[i] == 1:
                edges.append(np.array([mins[i], maxs[i]], dtype=float))
            else:
                edges.append(
                    np.linspace(mins[i], maxs[i], counts[i] + 1, dtype=float)
                )

        return (counts[0], counts[1], counts[2]), (
            edges[0],
            edges[1],
            edges[2],
        )

    @staticmethod
    def _clip_mesh_to_box(
        mesh: trimesh.Trimesh,
        x0: float, y0: float, z0: float,
        x1: float, y1: float, z1: float,
    ) -> trimesh.Trimesh:
        """Clip *mesh* to an axis-aligned box using six plane slices."""
        result = mesh
        planes = [
            ([1, 0, 0], [x0, 0, 0]),   # x >= x0
            ([-1, 0, 0], [x1, 0, 0]),   # x <= x1
            ([0, 1, 0], [0, y0, 0]),     # y >= y0
            ([0, -1, 0], [0, y1, 0]),    # y <= y1
            ([0, 0, 1], [0, 0, z0]),     # z >= z0
            ([0, 0, -1], [0, 0, z1]),    # z <= z1
        ]
        for normal, point in planes:
            result = trimesh.intersections.slice_mesh_plane(
                result, normal, point
            )
            if result.is_empty:
                return result
        return result

    def _slice_into_chunks(
        self,
        mesh: trimesh.Trimesh,
        model_bounds: np.ndarray,
        grid_counts: Tuple[int, int, int],
        grid_edges: Tuple[np.ndarray, np.ndarray, np.ndarray],
    ) -> List[Chunk]:
        mins, maxs = model_bounds
        chunks: List[Chunk] = []

        x_edges, y_edges, z_edges = grid_edges
        nx, ny, nz = grid_counts

        # Small epsilon to classify interior cut faces.
        eps = 1e-5

        for i in range(nx):
            x0, x1 = float(x_edges[i]), float(x_edges[i + 1])
            for j in range(ny):
                y0, y1 = float(y_edges[j]), float(y_edges[j + 1])
                for k in range(nz):
                    z0, z1 = float(z_edges[k]), float(z_edges[k + 1])

                    cell_trimesh = self._clip_mesh_to_box(
                        mesh, x0, y0, z0, x1, y1, z1,
                    )
                    if cell_trimesh.is_empty:
                        continue

                    cb = cell_trimesh.bounds
                    cut_faces: List[str] = []

                    # Interior planes along each axis.
                    if x0 > mins[0] + eps:
                        cut_faces.append("-x")
                    if x1 < maxs[0] - eps:
                        cut_faces.append("+x")
                    if y0 > mins[1] + eps:
                        cut_faces.append("-y")
                    if y1 < maxs[1] - eps:
                        cut_faces.append("+y")
                    if z0 > mins[2] + eps:
                        cut_faces.append("-z")
                    if z1 < maxs[2] - eps:
                        cut_faces.append("+z")

                    chunk_id = f"chunk_{i}_{j}_{k}"
                    chunks.append(
                        Chunk(
                            chunk_id=chunk_id,
                            mesh=cell_trimesh,
                            position_in_grid=(i, j, k),
                            cut_faces=cut_faces,
                            bounding_box=cb,
                        )
                    )

        return chunks


def chunk_mesh(mesh: trimesh.Trimesh) -> List[ChunkMetadata]:
    """
    Backwards-compatible wrapper around :class:`ChunkEngine`.

    This returns legacy :class:`ChunkMetadata` entries corresponding to a
    single untransformed chunk containing the entire mesh. New code should
    use :class:`ChunkEngine` instead.
    """
    if mesh is None:
        raise ValueError("mesh must not be None")

    identity = np.eye(4, dtype=float)
    return [
        ChunkMetadata(
            id="chunk_0",
            transform=identity,
            connector_pairs=[],
        )
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chunk an STL model into print-sized pieces.")
    parser.add_argument(
        "stl_path",
        type=str,
        nargs="?",
        default="sample.stl",
        help="Path to input STL file (default: sample.stl in current directory).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Directory to write chunk STL files into.",
    )
    args = parser.parse_args()

    engine = ChunkEngine(args.stl_path, output_dir=args.output)
    try:
        chunks = engine.run()
    except Exception as exc:  # pragma: no cover - manual smoke path
        print(f"Chunking failed: {exc}")
    else:
        print(f"Created {len(chunks)} chunks in '{args.output}':")
        for c in chunks:
            print(f"  {c.chunk_id} at grid position {c.position_in_grid}, cut_faces={c.cut_faces}")

