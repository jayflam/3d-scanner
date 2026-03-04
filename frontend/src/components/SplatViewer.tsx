import { useEffect, useRef, useState } from "react";
import * as GaussianSplats3D from "@mkkellogg/gaussian-splats-3d";

interface SplatViewerProps {
  /** API endpoint URL that returns JSON with a `url` field pointing to the .ply file */
  exteriorUrl?: string | null;
  interiorUrl?: string | null;
}

export default function SplatViewer({ exteriorUrl, interiorUrl }: SplatViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<InstanceType<typeof GaussianSplats3D.Viewer> | null>(null);
  const [activeView, setActiveView] = useState<"exterior" | "interior">("exterior");
  const [isLoading, setIsLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentApiUrl = activeView === "exterior" ? exteriorUrl : interiorUrl;
  const hasExterior = !!exteriorUrl;
  const hasInterior = !!interiorUrl;

  useEffect(() => {
    if (!containerRef.current || !currentApiUrl) return;

    const container = containerRef.current;
    setIsLoading(true);
    setError(null);
    let cancelled = false;

    // Clean up previous viewer
    if (viewerRef.current) {
      try {
        viewerRef.current.dispose();
      } catch {
        // Ignore cleanup errors
      }
      viewerRef.current = null;
      container.innerHTML = "";
    }

    // First fetch the splat endpoint to get the actual .ply URL
    async function loadSplat() {
      try {
        const res = await fetch(currentApiUrl!);
        if (!res.ok) throw new Error(`Failed to fetch splat info: ${res.status}`);
        const data = await res.json();
        const splatFileUrl: string = data.url;

        if (cancelled) return;

        const viewer = new GaussianSplats3D.Viewer({
          cameraUp: [0, -1, 0],
          initialCameraPosition: [0, 0, 5],
          initialCameraLookAt: [0, 0, 0],
          rootElement: container,
          selfDrivenMode: true,
        });

        viewerRef.current = viewer;

        await viewer.addSplatScene(splatFileUrl, { showLoadingUI: false });
        if (!cancelled) {
          viewer.start();
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load splat");
          setIsLoading(false);
        }
      }
    }

    loadSplat();

    return () => {
      cancelled = true;
      if (viewerRef.current) {
        try {
          viewerRef.current.dispose();
        } catch {
          // Ignore cleanup errors
        }
        viewerRef.current = null;
      }
    };
  }, [currentApiUrl]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  if (!hasExterior && !hasInterior) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
        <CubeIcon className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <p className="text-sm text-slate-400">
          3D reconstruction not yet available
        </p>
        <p className="text-xs text-slate-500 mt-1">
          Splats will appear once processing completes
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <div className="flex gap-1">
          {hasExterior && (
            <button
              onClick={() => setActiveView("exterior")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                activeView === "exterior"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              Exterior
            </button>
          )}
          {hasInterior && (
            <button
              onClick={() => setActiveView("interior")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                activeView === "interior"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              Interior
            </button>
          )}
        </div>
        <button
          onClick={toggleFullscreen}
          className="p-1.5 text-slate-400 hover:text-slate-200 transition-colors"
          title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        >
          <FullscreenIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Viewer container */}
      <div
        ref={containerRef}
        className="relative w-full aspect-[4/3] bg-slate-950"
        style={{ touchAction: "none" }}
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-slate-400">Loading 3D model...</p>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10">
            <div className="text-center px-4">
              <p className="text-sm text-red-400">Failed to load 3D model</p>
              <p className="text-xs text-slate-500 mt-1">{error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// -- Inline icons ------------------------------------------------------------

function CubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  );
}

function FullscreenIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
    </svg>
  );
}
