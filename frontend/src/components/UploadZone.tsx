import { useCallback, useRef, useState } from "react";

interface UploadZoneProps {
  label: string;
  accept?: string;
  maxSizeMB?: number;
  file: File | null;
  uploadProgress: number | null;
  onFileSelect: (file: File) => void;
  onClear: () => void;
}

export default function UploadZone({
  label,
  accept = "video/*",
  maxSizeMB = 500,
  file,
  uploadProgress,
  onFileSelect,
  onClear,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateAndSelect = useCallback(
    (f: File) => {
      setError(null);
      const maxBytes = maxSizeMB * 1024 * 1024;
      if (f.size > maxBytes) {
        setError(`File exceeds ${maxSizeMB}MB limit`);
        return;
      }
      onFileSelect(f);
    },
    [maxSizeMB, onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) validateAndSelect(f);
    },
    [validateAndSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleClick = () => inputRef.current?.click();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) validateAndSelect(f);
  };

  const isUploading = uploadProgress !== null && uploadProgress < 100;

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">
        {label}
      </label>

      {!file ? (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={handleClick}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            isDragOver
              ? "border-blue-500 bg-blue-500/10"
              : "border-slate-700 hover:border-slate-600 bg-slate-800/50"
          }`}
        >
          <UploadIcon className="w-10 h-10 text-slate-500 mx-auto mb-3" />
          <p className="text-sm text-slate-400">
            <span className="text-blue-400 font-medium">Click to browse</span>{" "}
            or drag and drop
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Video files up to {maxSizeMB}MB
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleInputChange}
            className="hidden"
          />
        </div>
      ) : (
        <div className="border border-slate-700 rounded-xl p-4 bg-slate-800/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3 min-w-0">
              <VideoIcon className="w-5 h-5 text-blue-400 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-slate-200 truncate">{file.name}</p>
                <p className="text-xs text-slate-500">
                  {(file.size / (1024 * 1024)).toFixed(1)} MB
                </p>
              </div>
            </div>
            {!isUploading && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onClear();
                  setError(null);
                }}
                className="text-slate-500 hover:text-slate-300 transition-colors"
              >
                <XIcon className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Progress bar */}
          {uploadProgress !== null && (
            <div className="mt-3">
              <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    uploadProgress >= 100 ? "bg-emerald-500" : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, uploadProgress)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {uploadProgress >= 100 ? "Upload complete" : `Uploading... ${uploadProgress}%`}
              </p>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </div>
  );
}

// -- Inline icons ------------------------------------------------------------

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
    </svg>
  );
}

function VideoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
