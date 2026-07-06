import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { UploadCloud, Video } from "lucide-react";
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";

interface UploadDropzoneProps {
  selectedFile?: File | null;
  uploading: boolean;
  progress: number;
  onFile: (file: File) => void;
  onUpload: () => void;
}

export function UploadDropzone({ selectedFile, uploading, progress, onFile, onUpload }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onFile(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-lg border border-dashed p-6 transition",
        dragging ? "border-electric bg-electric/10 shadow-glow" : "border-line bg-white/5"
      )}
    >
      <input ref={inputRef} type="file" accept="video/*" className="hidden" onChange={handleInput} />
      <div className="flex flex-col items-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg bg-electric/12 text-electric">
          {selectedFile ? <Video className="h-8 w-8" /> : <UploadCloud className="h-8 w-8" />}
        </div>
        <h3 className="text-lg font-semibold text-white">{selectedFile ? selectedFile.name : "Drop a video file"}</h3>
        <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">MP4, MOV, AVI, MKV, WEBM, WMV, or FLV up to 500 MB.</p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()}>
            Choose file
          </Button>
          <Button type="button" disabled={!selectedFile} loading={uploading} onClick={onUpload}>
            Upload video
          </Button>
        </div>
      </div>
      {(uploading || progress > 0) && (
        <div className="mt-6">
          <div className="mb-2 flex justify-between text-xs text-slate-400">
            <span>Storage upload</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-electric transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
    </div>
  );
}
