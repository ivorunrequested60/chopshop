from __future__ import annotations

import numpy as np
import pytest
import trimesh

from chopshop.backend.core.connectors import (
    DEFAULT_CLEARANCE_MM,
    generate_dovetail_female,
    generate_dovetail_male,
    place_connectors,
)


WIDTH, DEPTH, LENGTH = 8.0, 4.0, 10.0

# +Z face of a 80 mm cube.
FACE_POINT = np.array([0.0, 0.0, 40.0])
FACE_NORMAL = np.array([0.0, 0.0, 1.0])


@pytest.fixture
def cube() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(80.0, 80.0, 80.0))


def test_male_dovetail_is_a_closed_positive_solid():
    """
    Regression test: the prism used to be wound inwards, which gave it a
    negative volume and made manifold3d reject every boolean it appeared in.
    """
    pin = generate_dovetail_male(WIDTH, DEPTH, LENGTH)

    assert pin.is_watertight
    assert pin.is_volume
    assert pin.volume > 0.0


def test_male_dovetail_volume_matches_the_analytic_frustum():
    """
    The prism tapers linearly from WIDTH x DEPTH at the base to 60% of that
    at the tip, so the volume is the integral of the cross-section.
    """
    pin = generate_dovetail_male(WIDTH, DEPTH, LENGTH)

    tip = 0.6
    # A(s) = (W - W(1-tip)s)(D - D(1-tip)s), integrated over s in [0, 1].
    a, b = WIDTH * (1 - tip), DEPTH * (1 - tip)
    expected = LENGTH * (WIDTH * DEPTH - (WIDTH * b + DEPTH * a) / 2 + a * b / 3)

    assert pin.volume == pytest.approx(expected, rel=1e-9)


def test_female_dovetail_is_larger_by_the_print_clearance():
    """The cavity is scaled up so an FDM print still slides together."""
    pin = generate_dovetail_male(WIDTH, DEPTH, LENGTH)
    socket = generate_dovetail_female(WIDTH, DEPTH, LENGTH)

    expected_scale = 1.0 + DEFAULT_CLEARANCE_MM / max(WIDTH, DEPTH, LENGTH)

    assert (socket.volume / pin.volume) ** (1 / 3) == pytest.approx(
        expected_scale, rel=1e-6
    )
    assert socket.volume > pin.volume


def test_male_connectors_add_pins_outside_the_cut_face(cube):
    """
    A 80 mm face with a 10 mm inset and 30 mm spacing gives a 3 x 3 grid, so
    the union must add exactly nine pins and extend the solid past the face.
    """
    pin = generate_dovetail_male(WIDTH, DEPTH, LENGTH)

    result = place_connectors(
        cube, (FACE_POINT, FACE_NORMAL), side="male",
        width=WIDTH, depth=DEPTH, length=LENGTH,
    )

    assert result.is_watertight
    assert result.volume - cube.volume == pytest.approx(9 * pin.volume, rel=1e-6)
    assert result.bounds[1][2] == pytest.approx(40.0 + LENGTH, abs=1e-6)


def test_female_connectors_cut_cavities_into_the_chunk(cube):
    """
    Regression test: the cavities used to be extruded away from the chunk, so
    the subtraction fell entirely outside the solid and removed nothing.
    """
    socket = generate_dovetail_female(WIDTH, DEPTH, LENGTH)

    result = place_connectors(
        cube, (FACE_POINT, FACE_NORMAL), side="female",
        width=WIDTH, depth=DEPTH, length=LENGTH,
    )

    assert result.is_watertight
    assert result.volume - cube.volume == pytest.approx(-9 * socket.volume, rel=1e-6)
    # Nothing was added on top of the face.
    assert result.bounds[1][2] == pytest.approx(40.0, abs=1e-6)


def test_a_mating_pair_leaves_clearance(cube):
    """The socket removes more material than the pin adds, by design."""
    male = place_connectors(cube, (FACE_POINT, FACE_NORMAL), side="male")
    female = place_connectors(cube, (FACE_POINT, FACE_NORMAL), side="female")

    added = male.volume - cube.volume
    removed = cube.volume - female.volume

    assert removed > added > 0.0


def test_face_too_small_for_the_inset_gets_no_connectors():
    """A 15 mm face cannot hold a 10 mm inset on both sides, so it is skipped."""
    small = trimesh.creation.box(extents=(15.0, 15.0, 15.0))

    result = place_connectors(
        small, (np.array([0.0, 0.0, 7.5]), FACE_NORMAL), side="male",
    )

    assert result.volume == pytest.approx(small.volume, rel=1e-9)
