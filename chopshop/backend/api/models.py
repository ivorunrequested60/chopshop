from __future__ import annotations

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class ChunkInfo(BaseModel):
    id: str
    grid_pos: Tuple[int, int, int]
    dimensions_mm: Tuple[float, float, float]
    stl_url: str
    estimated_minutes: float
    filament_grams: float
    status: Literal["queued", "printing", "done"]


class SplitResult(BaseModel):
    model_id: str
    total_chunks: int
    chunks: List[ChunkInfo] = Field(default_factory=list)
    total_estimated_minutes: float


class ProgressResponse(BaseModel):
    model_id: str
    chunks_done: int
    chunks_total: int
    pct_complete: float
    estimated_remaining_minutes: float


class UploadResponse(BaseModel):
    model_id: str


class ModelUpload(BaseModel):
    model_id: str
    filename: str
    path: str
    uploaded_at: Optional[str] = None

