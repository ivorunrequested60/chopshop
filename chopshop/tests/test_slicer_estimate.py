from __future__ import annotations

import pytest

from chopshop.backend.core.slicer_estimate import (
    PLA_DENSITY_G_PER_CM3,
    SlicerEstimator,
)


def test_heuristic_is_used_when_no_slicer_is_on_path(box_stl):
    """With an unknown CLI name the estimator falls back to geometry."""
    path, _ = box_stl(extents=(50.0, 50.0, 50.0))

    est = SlicerEstimator(orcaslicer_cmd="definitely-not-a-real-slicer").estimate(path)

    assert est.method == "heuristic"
    assert est.chunk_id == "model"
    assert est.estimated_minutes > 0.0
    assert est.filament_grams > 0.0
    assert est.filament_meters > 0.0


def test_heuristic_filament_mass_matches_volume_times_infill(box_stl):
    """
    Mass is the solid volume scaled by the infill fraction and PLA density.
    A 50 mm cube is 125 cm^3.
    """
    path, _ = box_stl(extents=(50.0, 50.0, 50.0))
    infill = 0.15

    est = SlicerEstimator(
        orcaslicer_cmd="definitely-not-a-real-slicer", infill_pct=infill
    ).estimate(path)

    assert est.filament_grams == pytest.approx(
        125.0 * infill * PLA_DENSITY_G_PER_CM3, rel=1e-4
    )


def test_grams_and_meters_round_trip():
    """Mass and length conversions are inverses for 1.75 mm PLA."""
    grams = 42.0
    meters = SlicerEstimator._grams_to_meters(grams)

    assert meters > 0.0
    assert SlicerEstimator._meters_to_grams(meters) == pytest.approx(grams, rel=1e-9)


def test_doubling_the_model_doubles_the_estimated_mass(box_stl, tmp_path):
    """Mass scales with volume, so 2x on every axis is 8x the filament."""
    small, _ = box_stl(extents=(20.0, 20.0, 20.0), name="small.stl")
    large, _ = box_stl(extents=(40.0, 40.0, 40.0), name="large.stl")

    estimator = SlicerEstimator(orcaslicer_cmd="definitely-not-a-real-slicer")
    a = estimator.estimate(small)
    b = estimator.estimate(large)

    assert b.filament_grams / a.filament_grams == pytest.approx(8.0, rel=1e-4)


def test_estimate_all_preserves_input_order(box_stl):
    a, _ = box_stl(extents=(20.0, 20.0, 20.0), name="a.stl")
    b, _ = box_stl(extents=(30.0, 30.0, 30.0), name="b.stl")
    c, _ = box_stl(extents=(40.0, 40.0, 40.0), name="c.stl")

    estimator = SlicerEstimator(orcaslicer_cmd="definitely-not-a-real-slicer")
    results = estimator.estimate_all([c, a, b])

    assert [r.chunk_id for r in results] == ["c", "a", "b"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SlicerEstimator().estimate(tmp_path / "nope.stl")


@pytest.mark.parametrize(
    "text, minutes",
    [
        ("Estimated printing time: 2h 30m", 150.0),
        ("Estimated printing time (normal mode): 45m", 45.0),
        ("; TIME: 9000", 150.0),
    ],
)
def test_slicer_time_strings_are_parsed(text, minutes):
    parsed, _, _ = SlicerEstimator()._parse_slicer_output(text)
    assert parsed == pytest.approx(minutes)


def test_slicer_filament_string_is_parsed():
    _, grams, meters = SlicerEstimator()._parse_slicer_output(
        "Filament used: 12.3 g (4.56 m)"
    )
    assert grams == pytest.approx(12.3)
    assert meters == pytest.approx(4.56)
