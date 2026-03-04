import { useState } from "react";

interface VideoPlayerProps {
  exteriorUrl?: string | null;
  interiorUrl?: string | null;
}

export default function VideoPlayer({ exteriorUrl, interiorUrl }: VideoPlayerProps) {
  const [activeView, setActiveView] = useState<"exterior" | "interior">("exterior");
  const hasExterior = !!exteriorUrl;
  const hasInterior = !!interiorUrl;
  const currentUrl = activeView === "exterior" ? exteriorUrl : interiorUrl;

  if (!hasExterior && !hasInterior) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-800">
        <span className="text-xs font-medium text-slate-400 mr-2">Video</span>
        {hasExterior && (
          <button
            onClick={() => setActiveView("exterior")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
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
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeView === "interior"
                ? "bg-blue-600 text-white"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            Interior
          </button>
        )}
      </div>

      {/* Video element */}
      {currentUrl ? (
        <video
          key={currentUrl}
          controls
          className="w-full aspect-video bg-black"
          preload="metadata"
        >
          <source src={currentUrl} type="video/mp4" />
          Your browser does not support the video element.
        </video>
      ) : (
        <div className="w-full aspect-video bg-slate-950 flex items-center justify-center">
          <p className="text-sm text-slate-500">No {activeView} video available</p>
        </div>
      )}
    </div>
  );
}
