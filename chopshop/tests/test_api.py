from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient backed by a throwaway data directory."""
    monkeypatch.setenv("CHOPSHOP_DATA_DIR", str(tmp_path / "data"))

    from chopshop.backend import config
    from chopshop.backend.api import routes, server

    importlib.reload(config)
    importlib.reload(routes)
    importlib.reload(server)

    with TestClient(server.create_app()) as c:
        yield c


def test_upload_split_and_track(client, stl_bytes):
    """Walk the full path a user takes through the app."""
    data = stl_bytes(extents=(400.0, 100.0, 100.0))

    upload = client.post("/api/upload", files={"file": ("big.stl", data)})
    assert upload.status_code == 200
    model_id = upload.json()["model_id"]

    split = client.post(f"/api/split/{model_id}")
    assert split.status_code == 200
    body = split.json()

    assert body["total_chunks"] == 3
    assert len(body["chunks"]) == 3
    assert body["total_estimated_minutes"] > 0.0

    for chunk in body["chunks"]:
        assert chunk["status"] == "queued"
        assert chunk["estimated_minutes"] > 0.0
        # Regression test for the uncapped slices, which zeroed this out.
        assert chunk["filament_grams"] > 0.0
        assert max(chunk["dimensions_mm"]) <= 170.0
    assert body["total_estimated_minutes"] == pytest.approx(
        sum(c["estimated_minutes"] for c in body["chunks"]), rel=1e-9
    )

    listed = client.get(f"/api/chunks/{model_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 3

    first = body["chunks"][0]["id"]
    stl = client.get(f"/api/chunks/{model_id}/{first}/stl")
    assert stl.status_code == 200
    assert stl.content.startswith(b"solid") or len(stl.content) > 84

    before = client.get(f"/api/progress/{model_id}").json()
    assert before["chunks_done"] == 0
    assert before["pct_complete"] == 0.0

    patched = client.patch(
        f"/api/chunks/{model_id}/{first}/status", json={"status": "done"}
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"

    after = client.get(f"/api/progress/{model_id}").json()
    assert after["chunks_done"] == 1
    assert after["chunks_total"] == 3
    assert after["pct_complete"] == pytest.approx(100 / 3)
    assert after["estimated_remaining_minutes"] < before["estimated_remaining_minutes"]


def test_two_models_keep_separate_chunk_rows(client, stl_bytes):
    """
    Chunk ids are grid coordinates and repeat across models. Splitting a
    second model must not overwrite the first one's rows.
    """
    data = stl_bytes(extents=(400.0, 100.0, 100.0))

    ids = []
    for name in ("a.stl", "b.stl"):
        model_id = client.post("/api/upload", files={"file": (name, data)}).json()["model_id"]
        client.post(f"/api/split/{model_id}")
        ids.append(model_id)

    for model_id in ids:
        assert len(client.get(f"/api/chunks/{model_id}").json()) == 3


def test_upload_rejects_non_stl(client):
    r = client.post("/api/upload", files={"file": ("notes.txt", b"hello")})
    assert r.status_code == 400


def test_upload_rejects_empty_file(client):
    r = client.post("/api/upload", files={"file": ("empty.stl", b"")})
    assert r.status_code == 400


def test_unknown_model_is_404(client):
    assert client.post("/api/split/does-not-exist").status_code == 404
    assert client.get("/api/chunks/does-not-exist").status_code == 404
    assert client.get("/api/progress/does-not-exist").status_code == 404


def test_invalid_chunk_status_is_rejected(client, stl_bytes):
    model_id = client.post(
        "/api/upload", files={"file": ("m.stl", stl_bytes((50.0, 50.0, 50.0)))}
    ).json()["model_id"]
    client.post(f"/api/split/{model_id}")

    r = client.patch(
        f"/api/chunks/{model_id}/chunk_0_0_0/status", json={"status": "exploded"}
    )
    assert r.status_code == 400
