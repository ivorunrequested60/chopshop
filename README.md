> This repository supersedes [utosrad/AutoSlicer3D](https://github.com/utosrad/AutoSlicer3D), which is archived. Same project, clean history.

# ChopShop

Splits a 3D model that does not fit your printer into printable chunks, generates the dovetail joints that hold them back together, and estimates the time and filament for each piece.

## Screenshot

<!--
  TODO (owner): record this and drop it in as docs/demo.gif, then replace the
  line below with:  ![ChopShop](docs/demo.gif)

  Record a single ~20 second GIF at 1280x800, browser window only, no desktop
  or bookmarks bar. Run the backend and `npm run dev`, then capture one
  continuous pass through all three views:

  1. Upload view. Drag an oversized STL onto the drop zone. Let the 3D preview
     load so the model is visibly larger than the green 180 mm wireframe build
     volume cube. Hold for ~2s so the mismatch is obvious. Click "Upload and
     continue".
  2. Split view. Wait for the exploded chunk layout to finish rendering.
     Drag once to orbit the camera so the pieces read as separate solids.
     Click one chunk so the right sidebar fills in with its ID, its
     width/depth/height in mm, its print time and its filament grams.
  3. Print tracker. Click "Start printing", then advance two chunks from
     queued to printing to done so the progress bar and the remaining-time
     figure both visibly move.

  Also save a single still frame of the split view as docs/split-view.png.
  That is the one image worth having if the GIF is too heavy to inline.
-->

_Screenshot pending. See the comment in this file for exactly what to record._

## What it does

A Bambu Lab A1 Mini has a 180 mm build volume. A helmet does not fit in it. ChopShop takes the STL, works out the smallest grid of pieces that each fit, cuts them, and tells you what each piece costs to print.

Concretely:

- **Grid sizing.** The chunk grid is the minimum that fits: `ceil(extent / 170)` per axis, where 170 mm is the 180 mm build cube minus a 10 mm margin. A 400 x 120 x 120 mm model becomes a 3 x 1 x 1 grid. A 400 x 400 x 250 mm model becomes 3 x 3 x 2, or 18 pieces.
- **Cutting.** Each cell is carved out of the source mesh with six capped plane slices, one per box face. Capping matters: without it the interior pieces come back as open shells with no volume, and every downstream estimate reads zero. Chunk volumes sum back to the source volume exactly.
- **Cut-face tracking.** Each chunk records which of its six faces are artificial cuts rather than original model surface, as `+x`, `-x`, `+y` and so on. Those are the faces that need joints. Outer faces are never labelled.
- **Joints.** Dovetail pins and sockets, laid out on a 30 mm grid across the cut face with a 10 mm inset from the edges. Each candidate site is ray-cast into the chunk first and skipped unless there is at least 5 mm of material behind it. Sockets are scaled up by 0.2 mm of clearance so an FDM print still slides together. Booleans go through manifold3d.
- **Estimates.** If the OrcaSlicer CLI is on `PATH`, ChopShop shells out to it and parses the real print time and filament usage out of its output or the resulting G-code comments. If it is not, it falls back to a geometric heuristic from mesh volume and surface area at a configurable infill.
- **Tracking.** Every chunk is a row in SQLite with a `queued` / `printing` / `done` status. The progress endpoint reports pieces completed and estimated minutes remaining.

Worked example, from an actual run against a generated 400 x 120 x 120 mm box with no slicer installed, at the default 15% infill:

```
chunk_0_0_0   133.3 x 120.0 x 120.0 mm   998.4 min   357.1 g
chunk_1_0_0   133.3 x 120.0 x 120.0 mm   998.4 min   357.1 g
chunk_2_0_0   133.3 x 120.0 x 120.0 mm   998.4 min   357.1 g
```

Those minutes come from the fallback heuristic, not from a slicer, and are not calibrated against a real print. Install OrcaSlicer if you want numbers you can trust.

Bring your own STL. No model is committed to this repository.

## Quickstart

Three commands. Verified on CPython 3.14 and Node 22, macOS arm64.

```bash
# 1. install the backend
python3 -m venv .venv && .venv/bin/pip install -r chopshop/backend/requirements.txt

# 2. start the API on :8000
.venv/bin/uvicorn chopshop.backend.api.server:app --reload --port 8000

# 3. in a second terminal, start the UI on :5173
cd chopshop/frontend && npm install && npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

Uploads, generated chunk STLs and the SQLite file all land in `data/` at the repository root. Set `CHOPSHOP_DATA_DIR` to put them somewhere else. Paths resolve from the package, not the working directory, so `uvicorn` runs from anywhere.

Run the tests with `.venv/bin/pytest`.

## How it works

```
  browser                    FastAPI                    geometry
  ───────                    ───────                    ────────

  UploadView
  drag an STL,
  preview it against  ──POST /api/upload──▶  write data/uploads/<id>/model.stl
  a 180 mm wireframe                         insert a row in models
  build volume                                      │
                                                    ▼
  SplitView                                  ChunkEngine (chunker.py)
  auto-fires the      ──POST /api/split/<id>─▶ load, fix normals, fill holes
  split on mount                              ceil(extent / 170) per axis
                                              6 capped plane slices per cell
                                              label the interior cut faces
                                                    │
                                                    ▼
                                             place_connectors (connectors.py)
                                             30 mm grid, 10 mm inset
                                             ray-cast for >= 5 mm of material
                                             union pins / subtract sockets
                                             via manifold3d      [not wired
                                                    │            into /split]
                                                    ▼
                                             SlicerEstimator (slicer_estimate.py)
                                             OrcaSlicer CLI if on PATH,
                                             else volume + area heuristic
                                             4 chunks at a time
                                                    │
                                                    ▼
                                             write data/chunks/<id>/*.stl
                                             insert chunk rows, status=queued
                                                    │
  exploded 3D view    ◀───SplitResult────────────────┘
  of every chunk,
  per-chunk mm /
  minutes / grams
        │
        ▼
  PrintTracker        ──PATCH .../status──▶  queued -> printing -> done
  progress bar,       ──GET /api/progress──▶ pieces done, minutes remaining
  per-chunk buttons

  AssemblyView        placeholder component, not yet routed
```

The API surface is six endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/upload` | Store an STL, return a model id |
| POST | `/api/split/{model_id}` | Chunk it, estimate it, persist it |
| GET | `/api/chunks/{model_id}` | List chunks with dimensions and estimates |
| GET | `/api/chunks/{model_id}/{chunk_id}/stl` | Download one chunk |
| PATCH | `/api/chunks/{model_id}/{chunk_id}/status` | Move a chunk through the print queue |
| GET | `/api/progress/{model_id}` | Pieces done and minutes remaining |

Interactive docs at http://localhost:8000/docs.

### Layout

```
chopshop/
  backend/
    config.py                 data directory resolution
    api/
      server.py               app factory, CORS, SQLite schema
      routes.py               the six endpoints
      models.py               pydantic request and response types
    core/
      chunker.py              grid sizing and capped plane slicing
      connectors.py           dovetail generation and placement
      slicer_estimate.py      OrcaSlicer CLI wrapper and heuristic fallback
  frontend/src/
    App.tsx                   upload / split / track view switch
    lib/api.ts                typed fetch wrappers
    components/               UploadView, SplitView, PrintTracker, AssemblyView
  tests/                      31 pytest tests
```

## Tests

```
$ pytest
31 passed
```

Everything runs off `trimesh` primitives, so there are no fixture files and nothing external to install. The suite checks the geometry against closed-form answers rather than golden outputs: chunk volumes must sum to the source volume, a dovetail's volume must match the analytic integral of its tapering cross-section, a male pass over an 80 mm face must add exactly nine pins, and a female pass must remove exactly nine sockets. The API test walks upload, split, list, download, mark-done and progress against a temporary data directory.

## Current limits

Worth knowing before you read the code:

- `place_connectors` works and is tested, but `/api/split` does not call it yet. Chunks come out as plain cut pieces with no joints.
- The cut plane is always axis-aligned. There is no seam optimisation, no attempt to hide cuts, and no check that a chunk is printable without supports.
- `AssemblyView` is a placeholder and is not routed.
- The heuristic estimator has not been calibrated against real prints. Treat its output as a rough ordering of chunks by cost, not as a print time.

## License

MIT. See [LICENSE](LICENSE).
