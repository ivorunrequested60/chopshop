from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import db_path
from .routes import router as chopshop_router


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    total_chunks INTEGER,
    total_estimated_minutes REAL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    grid_z INTEGER NOT NULL,
    dim_x_mm REAL NOT NULL,
    dim_y_mm REAL NOT NULL,
    dim_z_mm REAL NOT NULL,
    stl_rel_path TEXT NOT NULL,
    estimated_minutes REAL NOT NULL,
    filament_grams REAL NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (model_id, chunk_id),
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
);
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    path = app.state.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ChopShop", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.db_path = db_path()
    app.include_router(chopshop_router)
    return app


app = create_app()
