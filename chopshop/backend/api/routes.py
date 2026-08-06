from __future__ import annotations

from pathlib import Path
from typing import Annotated, List, Tuple

import aiosqlite
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import (
    ChunkInfo,
    ModelUpload,
    ProgressResponse,
    SplitResult,
    UploadResponse,
)
from ..core.chunker import ChunkEngine
from ..core.slicer_estimate import SlicerEstimator


router = APIRouter(prefix="/api", tags=["autoslicer"])


def _get_db_path(request: Request) -> Path:
    db_path = getattr(request.app.state, "db_path", None)
    if db_path is None:
        raise RuntimeError("Database path is not configured on app.state.db_path")
    return Path(db_path)


class ChunkStatusUpdate(BaseModel):
    status: str


@router.post("/upload", response_model=UploadResponse)
async def upload_model(
    request: Request,
    file: Annotated[UploadFile, File(description="STL model")],
) -> UploadResponse:
    if file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename")

    db_path = _get_db_path(request)

    model_id = UploadFile.__name__  # placeholder to satisfy type checker
    from uuid import uuid4

    model_id = uuid4().hex
    upload_root = Path("output") / "uploads" / model_id
    upload_root.mkdir(parents=True, exist_ok=True)
    model_path = upload_root / "model.stl"

    contents = await file.read()
    await file.close()
    model_path.write_bytes(contents)

    from datetime import datetime, timezone

    uploaded_at = datetime.now(tz=timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO models (model_id, filename, original_path, uploaded_at, total_chunks, total_estimated_minutes)
            VALUES (?, ?, ?, ?, NULL, NULL)
            """,
            (model_id, file.filename, str(model_path), uploaded_at),
        )
        await db.commit()

    return UploadResponse(model_id=model_id)


async def _fetch_model_path(db_path: Path, model_id: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT original_path FROM models WHERE model_id = ?", (model_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Model not found",
                )
            return str(row["original_path"])


_slicer_estimator = SlicerEstimator()


@router.post("/split/{model_id}", response_model=SplitResult)
async def split_model(model_id: str, request: Request) -> SplitResult:
    db_path = _get_db_path(request)
    model_path = await _fetch_model_path(db_path, model_id)

    output_root = Path("output") / "chunks" / model_id
    output_root.mkdir(parents=True, exist_ok=True)

    try:
        engine = ChunkEngine(str(model_path), output_dir=output_root)
        chunks = engine.run()
    except Exception as exc:  # pragma: no cover - runtime safety
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chunking failed: {exc}",
        ) from exc

    # Collect STL paths for slicer estimation.
    stl_paths = [output_root / f"{chunk.chunk_id}.stl" for chunk in chunks]
    try:
        estimates = _slicer_estimator.estimate_all(stl_paths)
    except Exception:  # pragma: no cover - estimator fallback
        estimates = []

    estimate_by_id = {e.chunk_id: e for e in estimates}

    chunk_infos: List[ChunkInfo] = []
    total_estimated_minutes = 0.0

    async with aiosqlite.connect(db_path) as db:
        for chunk in chunks:
            est = estimate_by_id.get(chunk.chunk_id)
            if est is not None:
                est_minutes = float(est.estimated_minutes)
                filament_grams = float(est.filament_grams)
            else:
                est_minutes = 0.0
                filament_grams = 0.0

            total_estimated_minutes += est_minutes

            bounds = chunk.bounding_box
            dims_vec = bounds[1] - bounds[0]
            dim_x, dim_y, dim_z = (
                float(dims_vec[0]),
                float(dims_vec[1]),
                float(dims_vec[2]),
            )

            grid_x, grid_y, grid_z = chunk.position_in_grid
            stl_rel_path = f"chunks/{model_id}/{chunk.chunk_id}.stl"

            await db.execute(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id,
                    model_id,
                    grid_x,
                    grid_y,
                    grid_z,
                    dim_x_mm,
                    dim_y_mm,
                    dim_z_mm,
                    stl_rel_path,
                    estimated_minutes,
                    filament_grams,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    model_id,
                    int(grid_x),
                    int(grid_y),
                    int(grid_z),
                    dim_x,
                    dim_y,
                    dim_z,
                    stl_rel_path,
                    est_minutes,
                    filament_grams,
                    "queued",
                ),
            )

            chunk_infos.append(
                ChunkInfo(
                    id=chunk.chunk_id,
                    grid_pos=(int(grid_x), int(grid_y), int(grid_z)),
                    dimensions_mm=(dim_x, dim_y, dim_z),
                    stl_url=f"/api/chunks/{model_id}/{chunk.chunk_id}/stl",
                    estimated_minutes=est_minutes,
                    filament_grams=filament_grams,
                    status="queued",
                )
            )

        await db.execute(
            """
            UPDATE models
            SET total_chunks = ?, total_estimated_minutes = ?
            WHERE model_id = ?
            """,
            (len(chunk_infos), total_estimated_minutes, model_id),
        )
        await db.commit()

    return SplitResult(
        model_id=model_id,
        total_chunks=len(chunk_infos),
        chunks=chunk_infos,
        total_estimated_minutes=total_estimated_minutes,
    )


@router.get("/chunks/{model_id}", response_model=List[ChunkInfo])
async def list_chunks(model_id: str, request: Request) -> List[ChunkInfo]:
    db_path = _get_db_path(request)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
                chunk_id,
                grid_x,
                grid_y,
                grid_z,
                dim_x_mm,
                dim_y_mm,
                dim_z_mm,
                stl_rel_path,
                estimated_minutes,
                filament_grams,
                status
            FROM chunks
            WHERE model_id = ?
            """,
            (model_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chunks found for model",
        )

    chunks: List[ChunkInfo] = []
    for row in rows:
        grid_pos = (row["grid_x"], row["grid_y"], row["grid_z"])
        dims = (row["dim_x_mm"], row["dim_y_mm"], row["dim_z_mm"])
        chunk_id = row["chunk_id"]
        chunks.append(
            ChunkInfo(
                id=chunk_id,
                grid_pos=grid_pos,
                dimensions_mm=dims,
                stl_url=f"/api/chunks/{model_id}/{chunk_id}/stl",
                estimated_minutes=row["estimated_minutes"],
                filament_grams=row["filament_grams"],
                status=row["status"],
            )
        )

    return chunks


@router.patch("/chunks/{model_id}/{chunk_id}/status", response_model=ChunkInfo)
async def update_chunk_status(
    model_id: str,
    chunk_id: str,
    body: ChunkStatusUpdate,
    request: Request,
) -> ChunkInfo:
    if body.status not in {"queued", "printing", "done"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value",
        )

    db_path = _get_db_path(request)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE chunks
            SET status = ?
            WHERE chunk_id = ? AND model_id = ?
            """,
            (body.status, chunk_id, model_id),
        )
        await db.commit()

        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
                chunk_id,
                grid_x,
                grid_y,
                grid_z,
                dim_x_mm,
                dim_y_mm,
                dim_z_mm,
                stl_rel_path,
                estimated_minutes,
                filament_grams,
                status
            FROM chunks
            WHERE chunk_id = ? AND model_id = ?
            """,
            (chunk_id, model_id),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found",
        )

    grid_pos = (row["grid_x"], row["grid_y"], row["grid_z"])
    dims = (row["dim_x_mm"], row["dim_y_mm"], row["dim_z_mm"])

    return ChunkInfo(
        id=row["chunk_id"],
        grid_pos=grid_pos,
        dimensions_mm=dims,
        stl_url=f"/api/chunks/{model_id}/{chunk_id}/stl",
        estimated_minutes=row["estimated_minutes"],
        filament_grams=row["filament_grams"],
        status=row["status"],
    )


@router.get("/progress/{model_id}", response_model=ProgressResponse)
async def get_progress(model_id: str, request: Request) -> ProgressResponse:
    db_path = _get_db_path(request)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
                SUM(estimated_minutes) AS total_estimated,
                SUM(CASE WHEN status = 'done' THEN estimated_minutes ELSE 0 END) AS done_estimated
            FROM chunks
            WHERE model_id = ?
            """,
            (model_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None or row["total"] is None or row["total"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chunks found for model",
        )

    chunks_total = int(row["total"])
    chunks_done = int(row["done"] or 0)
    pct_complete = (chunks_done / chunks_total) * 100.0 if chunks_total else 0.0

    total_estimated = float(row["total_estimated"] or 0.0)
    done_estimated = float(row["done_estimated"] or 0.0)
    estimated_remaining = max(total_estimated - done_estimated, 0.0)

    return ProgressResponse(
        model_id=model_id,
        chunks_done=chunks_done,
        chunks_total=chunks_total,
        pct_complete=pct_complete,
        estimated_remaining_minutes=estimated_remaining,
    )


@router.get("/chunks/{model_id}/{chunk_id}/stl")
async def get_chunk_stl(model_id: str, chunk_id: str) -> FileResponse:
    stl_path = Path("output") / "chunks" / model_id / f"{chunk_id}.stl"
    if not stl_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk STL not found",
        )

    return FileResponse(
        path=stl_path,
        media_type="application/octet-stream",
        filename=f"{chunk_id}.stl",
    )

