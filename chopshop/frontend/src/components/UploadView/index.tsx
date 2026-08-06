import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Canvas, useFrame, useThree, useLoader } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Color, Mesh, PerspectiveCamera, Vector3 } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { uploadModel } from "../../lib/api";
import { ErrorBoundary } from "../ErrorBoundary";

type Props = {
  onUploaded: (modelId: string) => void;
};

type DragState = "idle" | "active";

function FitCameraToObject({ mesh }: { mesh: Mesh | null }) {
  const { camera } = useThree();

  useFrame(() => {
    if (!mesh) return;
    mesh.updateWorldMatrix(true, true);
    const box = mesh.geometry.boundingBox;
    if (!box) return;
    const size = new Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim === 0) return;

    const perspectiveCamera = camera as PerspectiveCamera;
    const fov = (perspectiveCamera.fov * Math.PI) / 180;
    const cameraZ = maxDim / (2 * Math.tan(fov / 2)) + maxDim;
    perspectiveCamera.position.set(0, 0, cameraZ);
    perspectiveCamera.lookAt(0, 0, 0);
  });

  return null;
}

function BuildVolumeBox() {
  const size: [number, number, number] = [180, 180, 180];
  return (
    <mesh>
      <boxGeometry args={size} />
      <meshBasicMaterial color="#22c55e" wireframe />
    </mesh>
  );
}

// UploadedModel receives a ready blob URL: never null, never a fake fallback.
function UploadedModel({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const [meshRef, setMeshRef] = useState<Mesh | null>(null);

  useMemo(() => {
    if (!geometry.boundingBox) geometry.computeBoundingBox();
  }, [geometry]);

  const scale = useMemo(() => {
    if (!geometry.boundingBox) return 1;
    const size = new Vector3();
    geometry.boundingBox.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim === 0) return 1;
    return 140 / maxDim;
  }, [geometry]);

  return (
    <>
      <mesh
        ref={setMeshRef}
        scale={scale}
        castShadow
        receiveShadow
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <primitive object={geometry} attach="geometry" />
        <meshStandardMaterial
          color={new Color("#3b82f6")}
          transparent
          opacity={0.6}
          metalness={0.1}
          roughness={0.4}
        />
      </mesh>
      <FitCameraToObject mesh={meshRef} />
    </>
  );
}

export function UploadView({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [dragState, setDragState] = useState<DragState>("idle");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Blob URL is created/revoked here, never inside a render-phase hook.
  useEffect(() => {
    if (!file) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    const next = files[0];
    if (!next.name.toLowerCase().endsWith(".stl")) {
      setError("Only .stl files are supported right now.");
      setFile(null);
      return;
    }
    setError(null);
    setSuccessMessage(null);
    setFile(next);
  }, []);

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(event.target.files);
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragState("idle");
    handleFiles(event.dataTransfer.files);
  };

  const onDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (dragState !== "active") setDragState("active");
  };

  const onDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragState("idle");
  };

  const onUpload = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await uploadModel(file);
      setSuccessMessage("Model uploaded successfully.");
      onUploaded(res.model_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setIsLoading(false);
    }
  };

  const dragClasses =
    dragState === "active"
      ? "border-blue-400 bg-blue-50/10"
      : "border-dashed border-gray-500/60 bg-gray-900/40";

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-white">Upload model</h2>
        <p className="text-sm text-gray-300">
          Drag and drop an STL file or use the file picker below. The green box
          shows the A1 Mini 180×180×180&nbsp;mm build volume.
        </p>
      </div>

      <div className="grid h-[480px] gap-4 md:grid-cols-2">
        <div
          className={`flex flex-col items-center justify-center rounded-lg border px-4 py-6 text-center text-gray-200 transition-colors ${dragClasses}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
        >
          <p className="mb-2 text-sm font-medium">
            {file ? file.name : "Drop STL here"}
          </p>
          <p className="mb-4 text-xs text-gray-400">
            Supported format: .stl (binary or ASCII)
          </p>
          <label className="inline-flex cursor-pointer items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
            <span>Select file</span>
            <input
              type="file"
              accept=".stl"
              className="hidden"
              onChange={onFileChange}
            />
          </label>
        </div>

        <ErrorBoundary
          fallback={
            <div className="flex h-full items-center justify-center rounded-lg border border-gray-700 bg-black/60 text-xs text-gray-400">
              3D preview unavailable for this file.
            </div>
          }
        >
          <div className="relative overflow-hidden rounded-lg border border-gray-700 bg-black/60">
            <Canvas
              camera={{ position: [0, 0, 300], fov: 45 }}
              shadows
              className="h-full w-full"
            >
              <color attach="background" args={["#020617"]} />
              <ambientLight intensity={0.3} />
              <directionalLight
                position={[100, 150, 200]}
                intensity={0.9}
                castShadow
              />
              <BuildVolumeBox />
              {objectUrl && (
                <Suspense fallback={null}>
                  <UploadedModel url={objectUrl} />
                </Suspense>
              )}
              <OrbitControls makeDefault />
            </Canvas>
          </div>
        </ErrorBoundary>
      </div>

      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={onUpload}
          disabled={!file || isLoading}
          className="inline-flex items-center justify-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-800/60"
        >
          {isLoading ? "Uploading…" : "Upload & Continue"}
        </button>
        <div className="min-h-[1.5rem] text-sm">
          {error && <span className="text-red-400">{error}</span>}
          {!error && successMessage && (
            <span className="text-emerald-400">{successMessage}</span>
          )}
        </div>
      </div>
    </div>
  );
}
