from __future__ import annotations

import io
from pathlib import Path

import pytest
import trimesh


@pytest.fixture
def box_stl(tmp_path: Path):
    """
    Write a watertight box STL and return (path, mesh).

    The default 400 x 100 x 100 mm box is longer than the 170 mm build cube
    along X only, so the expected chunk grid is 3 x 1 x 1.
    """

    def _make(extents=(400.0, 100.0, 100.0), name: str = "model.stl"):
        mesh = trimesh.creation.box(extents=extents)
        path = tmp_path / name
        mesh.export(path)
        return path, mesh

    return _make


@pytest.fixture
def stl_bytes():
    """Return the STL encoding of a box with the given extents."""

    def _make(extents=(400.0, 100.0, 100.0)) -> bytes:
        buf = io.BytesIO()
        trimesh.creation.box(extents=extents).export(buf, file_type="stl")
        return buf.getvalue()

    return _make
