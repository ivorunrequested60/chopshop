import { useState } from "react";
import { UploadView } from "./components/UploadView";
import { SplitView } from "./components/SplitView";
import { PrintTracker } from "./components/PrintTracker";
import { ErrorBoundary } from "./components/ErrorBoundary";

type View = "upload" | "split" | "track";

function App() {
  const [view, setView] = useState<View>("upload");
  const [modelId, setModelId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-2 border-b border-slate-800 pb-4 sm:flex-row sm:items-baseline sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              ChopShop
            </h1>
            <p className="mt-1 text-sm text-slate-300">
              Upload large STL models, split them into printable chunks, and
              track printing progress.
            </p>
          </div>
          <nav className="mt-2 flex gap-1 rounded-full border border-slate-800 bg-slate-900/60 p-1 text-xs font-medium text-slate-300 sm:mt-0">
            <span
              className={`cursor-pointer rounded-full px-3 py-1 ${
                view === "upload" ? "bg-slate-800 text-white" : ""
              }`}
            >
              Upload
            </span>
            <span
              className={`cursor-pointer rounded-full px-3 py-1 ${
                view === "split" ? "bg-slate-800 text-white" : ""
              }`}
            >
              Split
            </span>
            <span
              className={`cursor-pointer rounded-full px-3 py-1 ${
                view === "track" ? "bg-slate-800 text-white" : ""
              }`}
            >
              Track
            </span>
          </nav>
        </header>

        <main className="flex-1">
          <ErrorBoundary>
          {view === "upload" && (
            <UploadView
              onUploaded={(id) => {
                setModelId(id);
                setView("split");
              }}
            />
          )}
          {view === "split" && (
            <SplitView
              modelId={modelId}
              onStartPrinting={(id) => {
                setModelId(id);
                setView("track");
              }}
            />
          )}
          {view === "track" && <PrintTracker jobId={modelId} />}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default App;

