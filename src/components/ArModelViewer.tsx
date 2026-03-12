import { useEffect, useRef } from "react";

interface ArModelViewerProps {
  modelUrl: string | null;
}

declare global {
  // eslint-disable-next-line no-var
  var customElements: CustomElementRegistry;
}

export default function ArModelViewer({ modelUrl }: ArModelViewerProps) {
  const hasModel = !!modelUrl;
  const scriptRef = useRef<HTMLScriptElement | null>(null);

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

  if (!hasModel) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-sm text-slate-400">
        Preparing AR model…
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
        <p className="text-sm text-slate-200 font-medium">View in AR (beta)</p>
        <p className="text-xs text-slate-500">Move your phone to place the vehicle</p>
      </div>
      <div className="w-full aspect-[4/3] bg-slate-950">
        {/* eslint-disable-next-line react/no-unknown-property */}
        <model-viewer
          src={modelUrl ?? undefined}
          ar
          ar-modes="scene-viewer quick-look webxr"
          camera-controls
          auto-rotate
          shadow-intensity="1"
          style={{ width: "100%", height: "100%", backgroundColor: "transparent" }}
        />
      </div>
    </div>
  );
}

