import { useEffect, useMemo, useState } from "react";
import { ChunkInfo, ProgressResponse, getChunks, getProgress, updateChunkStatus } from "../../lib/api";

type ChunkStatus = "queued" | "printing" | "done";

type Props = {
  jobId: string | null;
};

function formatDuration(seconds: number): string {
  const clamped = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const secs = clamped % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

function getNextStatus(status: ChunkStatus): ChunkStatus {
  if (status === "queued") return "printing";
  if (status === "printing") return "done";
  return "queued";
}

export function PrintTracker({ jobId }: Props) {
  const [chunks, setChunks] = useState<ChunkInfo[]>([]);
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [printingStartTime, setPrintingStartTime] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    const load = async () => {
      try {
        const [chunksResult, progressResult] = await Promise.allSettled([
          getChunks(jobId),
          getProgress(jobId),
        ]);

        if (cancelled) return;

        if (chunksResult.status === "fulfilled") {
          setChunks(chunksResult.value);
        } else {
          setError("Failed to load chunks.");
        }

        if (progressResult.status === "fulfilled") {
          setProgress(progressResult.value);
        }

        setIsLoading(false);
      } catch (e) {
        if (cancelled) return;
        setError("Failed to load print progress.");
        setIsLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;

    const intervalId = window.setInterval(async () => {
      try {
        const latest = await getProgress(jobId);
        setProgress(latest);
      } catch {
        // ignore polling errors; a future poll may succeed
      }
    }, 10_000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [jobId]);

  useEffect(() => {
    if (!printingStartTime) return;

    const id = window.setInterval(() => {
      setNow(Date.now());
    }, 1_000);

    return () => {
      window.clearInterval(id);
    };
  }, [printingStartTime]);

  useEffect(() => {
    if (printingStartTime != null) return;
    const anyPrinting = chunks.some((c) => c.status === "printing");
    if (anyPrinting) {
      setPrintingStartTime(Date.now());
    }
  }, [chunks, printingStartTime]);

  const totalEstimatedSeconds = useMemo(
    () => chunks.reduce((sum, chunk) => sum + chunk.estimated_minutes * 60, 0),
    [chunks],
  );

  const doneEstimatedSeconds = useMemo(
    () =>
      chunks
        .filter((c) => c.status === "done")
        .reduce((sum, chunk) => sum + chunk.estimated_minutes * 60, 0),
    [chunks],
  );

  const percentComplete = useMemo(() => {
    if (progress) return progress.pct_complete;
    if (!totalEstimatedSeconds) return 0;
    return Math.min(100, (doneEstimatedSeconds / totalEstimatedSeconds) * 100);
  }, [progress, doneEstimatedSeconds, totalEstimatedSeconds]);

  const elapsedSeconds = useMemo(() => {
    if (progress) {
      return (progress.pct_complete / 100) * totalEstimatedSeconds;
    }
    if (printingStartTime) {
      return (now - printingStartTime) / 1000;
    }
    return 0;
  }, [progress, totalEstimatedSeconds, printingStartTime, now]);

  const remainingSeconds = useMemo(() => {
    if (progress) return progress.estimated_remaining_minutes * 60;
    return Math.max(0, totalEstimatedSeconds - elapsedSeconds);
  }, [progress, totalEstimatedSeconds, elapsedSeconds]);

  if (!jobId) return null;

  return (
    <section className="space-y-4">
      <div className="rounded-lg border border-gray-700 bg-slate-900/80 p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            Overall progress
          </h2>
          <span className="text-xs font-medium text-gray-300">
            {percentComplete.toFixed(0)}%
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
          <div
            className="h-full rounded-full bg-emerald-500 transition-[width] duration-500 ease-out"
            style={{ width: `${percentComplete}%` }}
          />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-gray-300">
          <div>
            <div className="font-medium text-gray-400">Total</div>
            <div className="font-semibold text-gray-100">
              {formatDuration(totalEstimatedSeconds)}
            </div>
          </div>
          <div>
            <div className="font-medium text-gray-400">Elapsed</div>
            <div className="font-semibold text-gray-100">{formatDuration(elapsedSeconds)}</div>
          </div>
          <div>
            <div className="font-medium text-gray-400">Remaining</div>
            <div className="font-semibold text-gray-100">
              {formatDuration(remainingSeconds)}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/60 bg-red-950/60 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-gray-700 bg-slate-900/80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Chunks</h3>
          {isLoading && (
            <span className="text-xs text-gray-400">Loading chunks...</span>
          )}
        </div>
        {chunks.length === 0 && !isLoading ? (
          <p className="text-sm text-gray-400">
            No chunks available for this job yet.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {chunks.map((chunk) => {
              const chunkStatus = chunk.status as ChunkStatus;
              const onClick = async () => {
                if (!jobId) return;
                const previousStatus = chunkStatus;
                const nextStatus = getNextStatus(previousStatus);

                setChunks((current) =>
                  current.map((c) =>
                    c.id === chunk.id ? { ...c, status: nextStatus } : c,
                  ),
                );

                if (nextStatus === "printing" && !printingStartTime) {
                  setPrintingStartTime(Date.now());
                }

                try {
                  await updateChunkStatus(jobId, chunk.id, nextStatus);
                } catch {
                  setChunks((current) =>
                    current.map((c) =>
                      c.id === chunk.id ? { ...c, status: previousStatus } : c,
                    ),
                  );
                  setError("Failed to update chunk status.");
                }
              };

              const badgeStyles =
                chunkStatus === "queued"
                  ? "bg-slate-700 text-gray-300"
                  : chunkStatus === "printing"
                    ? "bg-amber-900/80 text-amber-200"
                    : "bg-emerald-900/80 text-emerald-200";

              const badgeLabel =
                chunkStatus === "queued"
                  ? "Queued"
                  : chunkStatus === "printing"
                    ? "Printing"
                    : "Done";

              return (
                <button
                  key={chunk.id}
                  type="button"
                  onClick={onClick}
                  className="flex flex-col overflow-hidden rounded-lg border border-gray-700 bg-slate-800/80 text-left transition hover:-translate-y-0.5 hover:border-emerald-500/60 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                >
                  <div className="relative h-24 w-full bg-slate-900/60">
                    <div className="flex h-full w-full items-center justify-center text-[11px] font-medium uppercase tracking-wide text-gray-500">
                      No preview
                    </div>
                    <span
                      className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-[10px] font-semibold ${badgeStyles}`}
                    >
                      {badgeLabel}
                    </span>
                  </div>
                  <div className="flex flex-1 flex-col gap-1 p-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-gray-100">
                        Chunk {chunk.id}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-gray-400">
                      <span>{formatDuration(chunk.estimated_minutes * 60)}</span>
                      <span>{chunk.filament_grams.toFixed(1)}g filament</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
