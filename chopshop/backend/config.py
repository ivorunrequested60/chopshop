from __future__ import annotations

"""
Filesystem layout for runtime data.

Uploads, generated chunk STLs and the SQLite database all live under a single
data directory. That directory is resolved from the package location, not the
process working directory, so ``uvicorn`` can be started from anywhere.

Set ``CHOPSHOP_DATA_DIR`` to relocate it (useful for tests and deployments).
"""

import os
from pathlib import Path

# <repo root>/chopshop/backend/config.py -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = REPO_ROOT / "data"


def data_dir() -> Path:
    """Root directory for all runtime artefacts."""
    override = os.environ.get("CHOPSHOP_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_DATA_DIR


def db_path() -> Path:
    """Path to the SQLite database file."""
    return data_dir() / "chopshop.db"


def upload_dir(model_id: str) -> Path:
    """Directory holding the original STL for ``model_id``."""
    return data_dir() / "uploads" / model_id


def chunks_dir(model_id: str) -> Path:
    """Directory holding the generated chunk STLs for ``model_id``."""
    return data_dir() / "chunks" / model_id
