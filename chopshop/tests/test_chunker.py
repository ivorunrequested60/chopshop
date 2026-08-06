from __future__ import annotations

import numpy as np
import pytest
import trimesh

from chopshop.backend.core.chunker import MAX_BUILD_CUBE_MM, ChunkEngine


def test_mesh_that_fits_is_not_split(box_stl, tmp_path):
    """A model inside the build cube comes back as a single chunk."""
    path, mesh = box_stl(extents=(100.0, 100.0, 100.0))

    chunks = ChunkEngine(str(path), output_dir=tmp_path / "out").run()

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "chunk_0_0_0"
    assert chunks[0].cut_faces == []
    assert (tmp_path / "out" / "chunk_0_0_0.stl").is_file()


def test_grid_is_the_minimum_that_fits_the_build_cube(box_stl, tmp_path):
    """
    A 400 x 100 x 100 mm box needs ceil(400/170) = 3 divisions along X and
    one along Y and Z.
    """
    path, _ = box_stl(extents=(400.0, 100.0, 100.0))

    chunks = ChunkEngine(str(path), output_dir=tmp_path / "out").run()

    assert len(chunks) == 3
    assert sorted(c.position_in_grid for c in chunks) == [(0, 0, 0), (1, 0, 0), (2, 0, 0)]


def test_every_chunk_fits_the_build_volume(box_stl, tmp_path):
    """No chunk may exceed the printer's build cube on any axis."""
    path, _ = box_stl(extents=(400.0, 400.0, 250.0))

    chunks = ChunkEngine(str(path), output_dir=tmp_path / "out").run()

    assert len(chunks) == 3 * 3 * 2
    for chunk in chunks:
        extents = chunk.bounding_box[1] - chunk.bounding_box[0]
        assert np.all(extents <= MAX_BUILD_CUBE_MM + 1e-6), (
            f"{chunk.chunk_id} is {extents} mm"
        )


def test_chunks_are_watertight_and_conserve_volume(box_stl, tmp_path):
    """
    Every exported chunk must be a closed solid, and the chunk volumes must
    add back up to the source volume. This is the regression test for the
    uncapped plane slices, which produced open shells with zero volume.
    """
    out = tmp_path / "out"
    path, mesh = box_stl(extents=(400.0, 100.0, 100.0))

    chunks = ChunkEngine(str(path), output_dir=out).run()

    total = 0.0
    for chunk in chunks:
        exported = trimesh.load_mesh(out / f"{chunk.chunk_id}.stl")
        assert exported.is_watertight, f"{chunk.chunk_id} is not closed"
        assert exported.volume > 0.0
        total += exported.volume

    assert np.isclose(total, mesh.volume, rtol=1e-4), (
        f"chunk volumes sum to {total}, source is {mesh.volume}"
    )


def test_cut_faces_mark_only_interior_planes(box_stl, tmp_path):
    """
    The outer chunks of a 3 x 1 x 1 grid each have one artificial face; the
    middle chunk has two. Original model surfaces are never labelled.
    """
    path, _ = box_stl(extents=(400.0, 100.0, 100.0))

    chunks = {c.position_in_grid: c for c in ChunkEngine(str(path), output_dir=tmp_path / "out").run()}

    assert chunks[(0, 0, 0)].cut_faces == ["+x"]
    assert sorted(chunks[(1, 0, 0)].cut_faces) == ["+x", "-x"]
    assert chunks[(2, 0, 0)].cut_faces == ["-x"]


def test_custom_max_dimensions_change_the_grid(box_stl, tmp_path):
    """The build volume is configurable, not hard-coded at the call site."""
    path, _ = box_stl(extents=(400.0, 100.0, 100.0))

    chunks = ChunkEngine(
        str(path), max_dimensions=(100.0, 100.0, 100.0), output_dir=tmp_path / "out"
    ).run()

    assert len(chunks) == 4


def test_missing_file_raises(tmp_path):
    engine = ChunkEngine(str(tmp_path / "nope.stl"), output_dir=tmp_path / "out")
    with pytest.raises(FileNotFoundError):
        engine.run()


def test_bad_max_dimensions_raise(tmp_path):
    with pytest.raises(ValueError):
        ChunkEngine(str(tmp_path / "x.stl"), max_dimensions=(100.0, 100.0))
