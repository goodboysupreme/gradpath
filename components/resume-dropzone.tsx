"use client";

import { useCallback, useRef, useState } from "react";
import { FileText, FolderOpen, Trash2, Upload } from "lucide-react";

const MAX_RESUME_FILE_BYTES = 5 * 1024 * 1024;
const SUPPORTED_RESUME_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".bmp"];
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.bmp,application/pdf,image/png,image/jpeg,image/bmp";

function isSupportedResumeFile(file: File) {
  const name = file.name.toLowerCase();
  return SUPPORTED_RESUME_EXTENSIONS.some((extension) => name.endsWith(extension));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

type Props = {
  file: File | null;
  filename: string | null;
  onFile: (file: File | null) => void;
  onError: (message: string | null) => void;
};

export function ResumeDropzone({ file, filename, onFile, onError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);

  const applyFile = useCallback(
    (next: File | undefined | null) => {
      if (!next) return;
      if (next.size > MAX_RESUME_FILE_BYTES) {
        onError("Keep the resume file under 5MB.");
        return;
      }
      if (!isSupportedResumeFile(next)) {
        onError("Upload a PDF, PNG, JPG, JPEG, or BMP resume.");
        return;
      }
      onError(null);
      onFile(next);
    },
    [onError, onFile],
  );

  const clearFile = useCallback(() => {
    onFile(null);
    onError(null);
    if (inputRef.current) inputRef.current.value = "";
  }, [onError, onFile]);

  return (
    <div className="flex min-h-[430px] flex-col gap-3">
      <div
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.dataTransfer.dropEffect = "copy";
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          dragDepth.current = 0;
          setDragging(false);
          applyFile(e.dataTransfer.files?.[0]);
        }}
        className={`relative flex flex-1 flex-col items-center justify-center rounded-[22px] border border-dashed p-6 text-center transition-all duration-150 ${
          dragging
            ? "border-[#e1ff5f] bg-[#e1ff5f]/10 shadow-[inset_0_0_0_1px_rgba(225,255,95,0.25)]"
            : file
              ? "border-emerald-300/25 bg-emerald-400/[0.04]"
              : "border-white/15 bg-[#090a10]"
        }`}
      >
        {dragging && (
          <div className="pointer-events-none absolute inset-3 rounded-[18px] border border-[#e1ff5f]/40 bg-[#e1ff5f]/5" />
        )}

        {file && filename ? (
          <div className="relative z-[1] max-w-full px-2">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-[#e1ff5f] text-zinc-950">
              <FileText className="h-7 w-7" />
            </div>
            <div className="truncate text-sm font-semibold text-white" title={filename}>
              {filename}
            </div>
            <div className="mt-1 text-xs text-zinc-500">{formatBytes(file.size)} · ready to analyze</div>
            <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-medium text-zinc-200 transition-all duration-150 hover:border-white/20 hover:text-white"
              >
                <FolderOpen className="h-3.5 w-3.5" />
                Replace
              </button>
              <button
                type="button"
                onClick={clearFile}
                className="inline-flex items-center gap-2 rounded-2xl border border-rose-300/20 bg-rose-400/10 px-4 py-2 text-xs font-medium text-rose-200 transition-all duration-150 hover:bg-rose-400/15"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </button>
            </div>
          </div>
        ) : (
          <div className="relative z-[1]">
            <div className={`mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl border border-white/10 bg-white/[0.03] text-[#e1ff5f] transition-transform duration-150 ${dragging ? "scale-110" : ""}`}>
              <Upload className="h-7 w-7" />
            </div>
            <div className="text-sm font-semibold text-white">
              {dragging ? "Drop resume to upload" : "Drag & drop your resume"}
            </div>
            <div className="mt-1 text-xs text-zinc-500">PDF or image · max 5MB · OCR for scans</div>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#e1ff5f] px-5 py-2.5 text-xs font-black text-zinc-950 transition-all duration-150 hover:scale-[1.02] hover:bg-[#f0ff99]"
            >
              <FolderOpen className="h-3.5 w-3.5" />
              Pick file
            </button>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            applyFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
