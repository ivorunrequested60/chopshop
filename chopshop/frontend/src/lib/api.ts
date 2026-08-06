const API_BASE = "/api";

export type UploadResponse = {
  model_id: string;
};

export type ChunkInfo = {
  id: string;
  grid_pos: [number, number, number];
  dimensions_mm: [number, number, number];
  stl_url: string;
  estimated_minutes: number;
  filament_grams: number;
  status: string;
};

export type SplitResult = {
  model_id: string;
  total_chunks: number;
  total_estimated_minutes: number;
  chunks: ChunkInfo[];
};

export type ProgressResponse = {
  model_id: string;
  chunks_done: number;
  chunks_total: number;
  pct_complete: number;
  estimated_remaining_minutes: number;
};

function networkError(cause: unknown): Error {
  return new Error(
    `Cannot reach the backend — is it running on port 8000? (${cause instanceof Error ? cause.message : String(cause)})`,
  );
}

async function httpError(res: Response, fallback: string): Promise<Error> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return new Error(body.detail);
  } catch {
    // ignore parse errors
  }
  return new Error(`${fallback}: ${res.status}`);
}

export async function uploadModel(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
  } catch (cause) {
    throw networkError(cause);
  }

  if (!res.ok) {
    throw await httpError(res, "Upload failed");
  }

  return (await res.json()) as UploadResponse;
}

export async function splitModel(modelId: string): Promise<SplitResult> {
  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/split/${encodeURIComponent(modelId)}`,
      { method: "POST" },
    );
  } catch (cause) {
    throw networkError(cause);
  }

  if (!res.ok) {
    throw await httpError(res, "Split failed");
  }

  return (await res.json()) as SplitResult;
}

export async function getChunks(modelId: string): Promise<ChunkInfo[]> {
  const res = await fetch(
    `${API_BASE}/chunks/${encodeURIComponent(modelId)}`,
  );

  if (!res.ok) {
    throw new Error(`Chunks fetch failed: ${res.status}`);
  }

  return (await res.json()) as ChunkInfo[];
}

export async function updateChunkStatus(
  modelId: string,
  chunkId: string,
  status: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/chunks/${encodeURIComponent(modelId)}/${encodeURIComponent(chunkId)}/status`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );

  if (!res.ok) {
    throw new Error(`Update chunk status failed: ${res.status}`);
  }
}

export async function getProgress(modelId: string): Promise<ProgressResponse> {
  const res = await fetch(
    `${API_BASE}/progress/${encodeURIComponent(modelId)}`,
  );

  if (!res.ok) {
    throw new Error(`Progress fetch failed: ${res.status}`);
  }

  return (await res.json()) as ProgressResponse;
}
