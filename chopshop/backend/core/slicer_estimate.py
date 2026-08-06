from __future__ import annotations

"""
Integration with external slicer (OrcaSlicer CLI) to estimate print time.

If the OrcaSlicer CLI is not available on PATH or fails for a given file,
we fall back to a geometric heuristic based on mesh volume and surface area.
"""

from pathlib import Path
from typing import List, Optional, Sequence, Literal
import argparse
import concurrent.futures
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile

import trimesh
from pydantic import BaseModel


DEFAULT_ORCASLICER_CMD = "orca-slicer"
PLA_DENSITY_G_PER_CM3 = 1.24
DEFAULT_INFILL = 0.15  # 15% infill, expressed as fraction


class PrintEstimate(BaseModel):
    chunk_id: str
    estimated_minutes: float
    filament_grams: float
    filament_meters: float
    method: Literal["slicer", "heuristic"]


class SlicerEstimator:
    def __init__(
        self,
        orcaslicer_cmd: str = DEFAULT_ORCASLICER_CMD,
        profile_path: Optional[Path] = None,
        infill_pct: float = DEFAULT_INFILL,
    ) -> None:
        self.orcaslicer_cmd = orcaslicer_cmd
        self.profile_path = profile_path
        self.infill_pct = infill_pct

    # ---- Public API ----

    def estimate(self, stl_path: Path | str) -> PrintEstimate:
        path = Path(stl_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        chunk_id = path.stem

        slicer_cmd = self._find_orcaslicer()
        if slicer_cmd is not None:
            slicer_result = self._run_orcaslicer(slicer_cmd, path)
            if slicer_result is not None:
                minutes, grams, meters = slicer_result
                return PrintEstimate(
                    chunk_id=chunk_id,
                    estimated_minutes=minutes,
                    filament_grams=grams,
                    filament_meters=meters,
                    method="slicer",
                )

        minutes, grams, meters = self._heuristic_estimate(path)
        return PrintEstimate(
            chunk_id=chunk_id,
            estimated_minutes=minutes,
            filament_grams=grams,
            filament_meters=meters,
            method="heuristic",
        )

    def estimate_all(self, chunk_stl_paths: Sequence[Path | str]) -> List[PrintEstimate]:
        paths: List[Path] = [Path(p) for p in chunk_stl_paths]
        results: List[PrintEstimate] = []
        if not paths:
            return results

        max_workers = min(4, len(paths))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.estimate, p): p for p in paths
            }
            # Preserve input order
            for p in paths:
                # Find the future corresponding to this path
                for future, fp in future_to_path.items():
                    if fp == p:
                        results.append(future.result())
                        break
        return results

    # ---- Internal helpers ----

    def _find_orcaslicer(self) -> Optional[str]:
        return shutil.which(self.orcaslicer_cmd)

    def _run_orcaslicer(
        self,
        cmd: str,
        stl: Path,
    ) -> Optional[tuple[float, float, float]]:
        """
        Invoke OrcaSlicer CLI and attempt to parse estimated time and filament usage.

        Returns:
            (minutes, grams, meters) if successful, otherwise None.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            gcode_path = Path(tmpdir) / (stl.stem + ".gcode")

            cli_cmd = [
                cmd,
                "--export-gcode",
                "--info",
                "--output",
                str(gcode_path),
                str(stl),
            ]

            if self.profile_path is not None:
                cli_cmd.extend(["--load", str(self.profile_path)])

            try:
                proc = subprocess.run(
                    cli_cmd,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=300,
                )
            except (OSError, subprocess.SubprocessError, ValueError):
                return None

            if proc.returncode != 0:
                return None

            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            minutes, grams, meters = self._parse_slicer_output(stdout)

            # If stdout parsing failed, try gcode comments
            if minutes is None or grams is None or meters is None:
                if gcode_path.is_file():
                    try:
                        gcode_text = gcode_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        gcode_text = ""
                    g_minutes, g_grams, g_meters = self._parse_slicer_output(gcode_text)
                    minutes = minutes if minutes is not None else g_minutes
                    grams = grams if grams is not None else g_grams
                    meters = meters if meters is not None else g_meters

            # As a last resort, some Orca builds might output JSON on stderr
            if minutes is None or grams is None:
                parsed = self._parse_possible_json(stdout) or self._parse_possible_json(stderr)
                if parsed is not None:
                    j_minutes, j_grams, j_meters = parsed
                    if minutes is None:
                        minutes = j_minutes
                    if grams is None:
                        grams = j_grams
                    if meters is None:
                        meters = j_meters

            if minutes is None or grams is None:
                return None

            if meters is None:
                # Approximate from grams assuming PLA density and 1.75mm filament
                meters = self._grams_to_meters(grams)

            return minutes, grams, meters

    @staticmethod
    def _parse_possible_json(text: str) -> Optional[tuple[float, float, Optional[float]]]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        time_s = data.get("time_s")
        if time_s is None:
            time_s = data.get("time_seconds")
        filament_g = data.get("filament_grams")
        if filament_g is None:
            filament_g = data.get("filament_g")
        filament_m = data.get("filament_meters")
        if filament_m is None:
            filament_m = data.get("filament_m")

        if time_s is None or filament_g is None:
            return None

        minutes = float(time_s) / 60.0
        grams = float(filament_g)
        meters = float(filament_m) if filament_m is not None else None
        return minutes, grams, meters

    def _parse_slicer_output(
        self,
        text: str,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Parse human-readable OrcaSlicer output or G-code comments.

        Returns (minutes, grams, meters), where any field may be None if not
        found.
        """
        minutes: Optional[float] = None
        grams: Optional[float] = None
        meters: Optional[float] = None

        # Common patterns for time such as:
        # "Estimated printing time: 2h 30m", "Time: 1h 5m 30s", ";TIME: 9000"
        time_patterns = [
            r"Estimated printing time[^:]*:\s*(.+)",
            r"Time[^:]*:\s*(.+)",
            r";\s*estimated printing time[^:]*:\s*(.+)",
            r";\s*TIME:\s*([0-9]+)",
        ]

        for line in text.splitlines():
            stripped = line.strip()

            # Filament usage patterns, e.g. "Filament used: 12.3 g (45.6 m)"
            if grams is None or meters is None:
                filament_match = re.search(
                    r"Filament (used|usage)[^:]*:\s*([\d\.]+)\s*g(?:\s*\(([\d\.]+)\s*m\))?",
                    stripped,
                    flags=re.IGNORECASE,
                )
                if filament_match:
                    grams_val = float(filament_match.group(2))
                    grams = grams_val
                    if filament_match.group(3):
                        meters = float(filament_match.group(3))

                # Alternative format: "Filament: 12345.6mm"
                if grams is None and meters is None:
                    alt_match = re.search(
                        r"Filament[^:]*:\s*([\d\.]+)\s*mm",
                        stripped,
                        flags=re.IGNORECASE,
                    )
                    if alt_match:
                        mm_val = float(alt_match.group(1))
                        meters = mm_val / 1000.0
                        # Approximate grams from meters
                        grams = self._meters_to_grams(meters)

            if minutes is None:
                for pattern in time_patterns:
                    m = re.search(pattern, stripped, flags=re.IGNORECASE)
                    if not m:
                        continue

                    val = m.group(1)
                    # When pattern is ";TIME: 9000", val is seconds
                    if pattern.endswith(r"([0-9]+)"):
                        try:
                            seconds = float(val)
                            minutes = seconds / 60.0
                            break
                        except ValueError:
                            continue

                    # General text like "2h 30m 15s" or "45m"
                    h_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*h", val)
                    m_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*m", val)
                    s_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s", val)

                    total_minutes = 0.0
                    if h_match:
                        total_minutes += float(h_match.group(1)) * 60.0
                    if m_match:
                        total_minutes += float(m_match.group(1))
                    if s_match and not m_match and not h_match:
                        total_minutes += float(s_match.group(1)) / 60.0

                    if total_minutes > 0:
                        minutes = total_minutes
                        break

        return minutes, grams, meters

    def _heuristic_estimate(self, stl_path: Path) -> tuple[float, float, float]:
        mesh = trimesh.load_mesh(stl_path, force="mesh")

        # trimesh reports volume in mm^3 and area in mm^2 for typical meshes.
        volume_cm3 = float(mesh.volume) / 1000.0
        surface_area_cm2 = float(mesh.area) / 100.0

        infill = float(self.infill_pct)
        estimate_minutes = (volume_cm3 * infill * 2.5) + (surface_area_cm2 * 0.3)

        filament_grams = volume_cm3 * infill * PLA_DENSITY_G_PER_CM3
        filament_meters = self._grams_to_meters(filament_grams)

        return estimate_minutes, filament_grams, filament_meters

    @staticmethod
    def _grams_to_meters(grams: float) -> float:
        """
        Approximate filament length in meters for 1.75mm PLA filament.
        """
        # Convert grams to cubic centimeters using PLA density.
        volume_cm3 = grams / PLA_DENSITY_G_PER_CM3
        radius_cm = 0.175 / 2.0 / 10.0  # 1.75mm diameter -> cm radius
        cross_section_cm2 = math.pi * radius_cm * radius_cm
        length_cm = volume_cm3 / cross_section_cm2
        return length_cm / 100.0

    @staticmethod
    def _meters_to_grams(meters: float) -> float:
        """
        Approximate grams from filament length in meters for 1.75mm PLA filament.
        """
        length_cm = meters * 100.0
        radius_cm = 0.175 / 2.0 / 10.0
        cross_section_cm2 = math.pi * radius_cm * radius_cm
        volume_cm3 = length_cm * cross_section_cm2
        return volume_cm3 * PLA_DENSITY_G_PER_CM3


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate print time and filament usage for STL chunks "
        "using OrcaSlicer when available, otherwise a geometric heuristic.",
    )
    parser.add_argument(
        "stl_paths",
        nargs="+",
        help="Paths to STL chunk files (shell globs like output/chunk_*.stl are expanded by the shell).",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Optional OrcaSlicer profile file path.",
    )
    parser.add_argument(
        "--infill",
        type=float,
        default=DEFAULT_INFILL,
        help="Infill fraction for heuristic fallback (e.g. 0.15 for 15%%).",
    )
    parser.add_argument(
        "--orcaslicer-cmd",
        type=str,
        default=DEFAULT_ORCASLICER_CMD,
        help="OrcaSlicer CLI command name or path (default: orca-slicer).",
    )

    args = parser.parse_args(argv)

    profile_path = Path(args.profile) if args.profile is not None else None

    estimator = SlicerEstimator(
        orcaslicer_cmd=args.orcaslicer_cmd,
        profile_path=profile_path,
        infill_pct=args.infill,
    )

    try:
        estimates = estimator.estimate_all(args.stl_paths)
    except Exception as exc:  # pragma: no cover - CLI defensive
        print(f"Error while estimating: {exc}", file=sys.stderr)
        return 1

    # Emit JSON per line for easy downstream consumption.
    for estimate in estimates:
        print(estimate.model_dump_json())

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
