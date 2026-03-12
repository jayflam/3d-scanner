import { useCallback, useEffect, useRef, useState } from "react";

interface ArModelViewerProps {
  modelUrl: string | null;
}

export default function ArModelViewer({ modelUrl }: ArModelViewerProps) {
  const hasModel = !!modelUrl;
  const scriptRef = useRef<HTMLScriptElement | null>(null);
  const viewerRef = useRef<HTMLElement | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if ("customElements" in window && customElements.get("model-viewer")) {
      return;
    }

    const script = document.createElement("script");
    script.type = "module";
    script.src =
      "https://unpkg.com/@google/model-viewer@v4.0.0/dist/model-viewer.min.js";
    document.head.appendChild(script);
    scriptRef.current = script;

    return () => {
      if (scriptRef.current) {
        scriptRef.current.remove();
        scriptRef.current = null;
      }
    };
  }, []);

  const handleLoad = useCallback(() => {
    setIsLoading(false);
    setError(null);
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setError("Failed to load 3D model for AR");
  }, []);

  useEffect(() => {
    const el = viewerRef.current;
    if (!el) return;

    el.addEventListener("load", handleLoad);
    el.addEventListener("error", handleError);
    return () => {
      el.removeEventListener("load", handleLoad);
      el.removeEventListener("error", handleError);
    };
  }, [modelUrl, handleLoad, handleError]);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
  }, [modelUrl]);

  if (!hasModel) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-sm text-slate-400">
        Preparing AR model…
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <ArIcon className="w-4 h-4 text-emerald-400 shrink-0" />
          <p className="text-sm text-slate-200 font-medium truncate">View in AR</p>
        </div>
        <p className="text-xs text-slate-500 hidden sm:block shrink-0">
          Tap the AR icon to place the vehicle
        </p>
      </div>

      <div className="relative w-full aspect-[4/3] bg-slate-950">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-slate-600 border-t-emerald-500 rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-slate-400">Loading AR model…</p>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10">
            <div className="text-center px-4">
              <p className="text-sm text-red-400">{error}</p>
              <p className="text-xs text-slate-500 mt-1">
                The 3D splat viewer above is still available
              </p>
            </div>
          </div>
        )}

        <model-viewer
          ref={viewerRef}
          src={modelUrl ?? undefined}
          ar
          ar-modes="scene-viewer quick-look webxr"
          ar-scale="auto"
          ar-placement="floor"
          camera-controls
          touch-action="pan-y"
          auto-rotate
          rotation-per-second="20deg"
          interaction-prompt="auto"
          shadow-intensity="1"
          shadow-softness="0.5"
          exposure="1"
          camera-orbit="45deg 55deg auto"
          min-camera-orbit="auto auto auto"
          max-camera-orbit="Infinity 90deg auto"
          field-of-view="30deg"
          loading="eager"
          style={{
            width: "100%",
            height: "100%",
            backgroundColor: "transparent",
            "--poster-color": "transparent",
          } as React.CSSProperties}
        >
          <button
            slot="ar-button"
            className="absolute bottom-4 right-4 flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-sm font-medium rounded-lg shadow-lg transition-colors"
            style={{ zIndex: 10 }}
          >
            <ArIcon className="w-4 h-4" />
            View in AR
          </button>
        </model-viewer>
      </div>
    </div>
  );
}

function ArIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"
      />
    </svg>
  );
}
