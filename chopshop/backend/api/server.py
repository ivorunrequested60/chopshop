from __future__ import annotations

from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as autoslicer_router


def create_app() -> FastAPI:
    app = FastAPI(title="AutoSlicer3D", version="0.1.0")

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

    db_path = Path("chopshop") / "autoslicer.db"
    app.state.db_path = db_path

    @app.on_event("startup")
    async def init_db() -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(db_path) as db:
            await db.executescript(
                """
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
                    chunk_id TEXT PRIMARY KEY,
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
                    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
                );
                """
            )
            await db.commit()

    app.include_router(autoslicer_router)
    return app


app = create_app()

