import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { ErrorBoundary } from "../ErrorBoundary";
import { Color, Vector3 } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { ChunkInfo, SplitResult, splitModel } from "../../lib/api";

type Props = {
  modelId: string | null;
  onStartPrinting: (modelId: string) => void;
};

type SplitState = "idle" | "splitting" | "ready" | "error";

type ChunkMeshProps = {
  chunk: ChunkInfo;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
};

function ChunkMesh({ chunk, index, isSelected, onSelect }: ChunkMeshProps) {
  const geometry = useLoader(STLLoader, chunk.stl_url);

  const spacing = 20;
  const row = Math.floor(index / 3);
  const col = index % 3;
  const offset: [number, number, number] = [
    (col - 1) * spacing,
    (row - 1) * spacing,
    0,
  ];

  const colorPalette = ["#22c55e", "#3b82f6", "#eab308", "#ec4899"];
  const color = colorPalette[index % colorPalette.length];

  if (!geometry.boundingBox) {
    geometry.computeBoundingBox();
  }
  const size = new Vector3();
  geometry.boundingBox?.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  const target = 120;
  const scale = maxDim > 0 ? target / maxDim : 1;

  return (
    <mesh
      position={offset}
      scale={scale}
      onClick={onSelect}
      castShadow
      receiveShadow
    >
      <primitive object={geometry} attach="geometry" />
      <meshStandardMaterial
        color={new Color(color)}
        metalness={0.1}
        roughness={0.5}
        opacity={isSelected ? 1 : 0.8}
        transparent
      />
    </mesh>
  );
}

export function SplitView({ modelId, onStartPrinting }: Props) {
  const [split, setSplit] = useState<SplitResult | null>(null);
  const [chunks, setChunks] = useState<ChunkInfo[]>([]);
  const [state, setState] = useState<SplitState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!modelId) return;

    const run = async () => {
      setState("splitting");
      setError(null);
      try {
        const splitResult = await splitModel(modelId);
        if (cancelled) return;
        setSplit(splitResult);
        setChunks(splitResult.chunks);
        setSelectedChunkId(splitResult.chunks[0]?.id ?? null);
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof Error ? e.message : "Failed to split model or load chunks",
        );
        setState("error");
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [modelId]);

  const selectedChunk = useMemo(
    () => chunks.find((c) => c.id === selectedChunkId) ?? chunks[0] ?? null,
    [chunks, selectedChunkId],
  );

  if (!modelId) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-gray-300">
        <p className="text-sm">Upload a model first to see its chunks.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-white">Split view</h2>
        <p className="text-sm text-gray-300">
          Exploded view of all printable chunks. Click a chunk or a row in the
          list to inspect its stats.
        </p>
      </div>

      <div className="grid min-h-[520px] flex-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <ErrorBoundary
          fallback={
            <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-gray-700 bg-black/60 text-xs text-gray-400">
              3D preview unavailable.
            </div>
          }
        >
          <div className="relative overflow-hidden rounded-lg border border-gray-700 bg-black/60">
            <Canvas
              camera={{ position: [0, 0, 260], fov: 45 }}
              shadows
              className="h-full w-full"
            >
              <color attach="background" args={["#020617"]} />
              <ambientLight intensity={0.3} />
              <directionalLight
                position={[120, 150, 200]}
                intensity={0.9}
                castShadow
              />
              <Suspense fallback={null}>
                {chunks.map((chunk, index) => (
                  <ChunkMesh
                    key={chunk.id}
                    chunk={chunk}
                    index={index}
                    isSelected={chunk.id === selectedChunk?.id}
                    onSelect={() => setSelectedChunkId(chunk.id)}
                  />
                ))}
              </Suspense>
              <OrbitControls makeDefault />
            </Canvas>
            {state === "splitting" && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/40">
                <p className="rounded-md bg-gray-900/80 px-4 py-2 text-sm text-gray-100">
                  Splitting model into chunks…
                </p>
              </div>
            )}
          </div>
        </ErrorBoundary>

        <aside className="flex flex-col gap-3 rounded-lg border border-gray-700 bg-slate-900/80 p-4 text-sm text-gray-100">
          <div className="flex flex-col gap-1 border-b border-gray-700 pb-3">
            <h3 className="text-base font-semibold text-white">
              Model summary
            </h3>
            {split ? (
              <div className="grid grid-cols-2 gap-2 text-xs sm:text-sm">
                <div>
                  <div className="text-gray-400">Total chunks</div>
                  <div className="font-medium">{split.total_chunks}</div>
                </div>
                <div>
                  <div className="text-gray-400">Total time</div>
                  <div className="font-medium">
                    {Math.round(split.total_estimated_minutes)} min
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-400">
                {state === "splitting"
                  ? "Calculating chunk layout and estimates…"
                  : "Waiting for split results."}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2 border-b border-gray-700 pb-3">
            <h3 className="text-base font-semibold text-white">
              Selected chunk
            </h3>
            {selectedChunk ? (
              <div className="space-y-1 text-xs sm:text-sm">
                <div>
                  <span className="text-gray-400">ID:</span>{" "}
                  <span className="font-mono text-gray-100">
                    {selectedChunk.id}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <div className="text-gray-400">Width</div>
                    <div className="font-medium">
                      {selectedChunk.dimensions_mm[0].toFixed(1)} mm
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Depth</div>
                    <div className="font-medium">
                      {selectedChunk.dimensions_mm[1].toFixed(1)} mm
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Height</div>
                    <div className="font-medium">
                      {selectedChunk.dimensions_mm[2].toFixed(1)} mm
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-gray-400">Print time</div>
                    <div className="font-medium">
                      {Math.round(selectedChunk.estimated_minutes)} min
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Filament</div>
                    <div className="font-medium">
                      {selectedChunk.filament_grams.toFixed(1)} g
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-400">
                {state === "splitting"
                  ? "Preparing chunks…"
                  : "Select a chunk from the list."}
              </p>
            )}
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto">
            <h3 className="text-base font-semibold text-white">Chunks</h3>
            {chunks.length === 0 ? (
              <p className="text-xs text-gray-400">
                {state === "splitting"
                  ? "Generating chunks…"
                  : "No chunks available."}
              </p>
            ) : (
              <ul className="divide-y divide-gray-800 rounded-md border border-gray-800 bg-slate-950/40">
                {chunks.map((chunk) => {
                  const isSelected = chunk.id === selectedChunk?.id;
                  return (
                    <li
                      key={chunk.id}
                      className={`flex cursor-pointer items-center justify-between px-3 py-2 text-xs sm:text-sm ${
                        isSelected ? "bg-slate-800/80" : "hover:bg-slate-900/80"
                      }`}
                      onClick={() => setSelectedChunkId(chunk.id)}
                    >
                      <div className="flex flex-col">
                        <span className="font-mono text-gray-100">
                          {chunk.id}
                        </span>
                        <span className="text-[11px] text-gray-400">
                          {chunk.dimensions_mm[0].toFixed(0)}×
                          {chunk.dimensions_mm[1].toFixed(0)}×
                          {chunk.dimensions_mm[2].toFixed(0)} mm
                        </span>
                      </div>
                      <div className="text-right text-[11px] text-gray-300">
                        <div>{Math.round(chunk.estimated_minutes)} min</div>
                        <div>{chunk.filament_grams.toFixed(0)} g</div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {error && (
            <div className="rounded-md border border-red-500/60 bg-red-950/60 px-3 py-2 text-xs text-red-200">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={() => onStartPrinting(modelId)}
            disabled={
              !modelId || state === "splitting" || chunks.length === 0
            }
            className="mt-1 inline-flex items-center justify-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-800/70"
          >
            Start printing
          </button>
        </aside>
      </div>
    </div>
  );
}

