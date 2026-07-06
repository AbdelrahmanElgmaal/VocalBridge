import { CheckCircle2, Clock3, FileAudio, FolderUp, Mic, Radio, UploadCloud, Video, XCircle } from "lucide-react";
import { getJobMediaKind, getJobSourceType, type MediaKind, type SourceKind } from "../../lib/mediaDashboard";
import { normalizeStatus } from "../../lib/status";
import type { TranslationDto, TranslationStatus } from "../../types/api";
import { Badge } from "./Badge";

export function MediaTypeBadge({ type }: { type: MediaKind }) {
  const Icon = type === "Video" ? Video : FileAudio;
  return (
    <Badge toneKey={type}>
      <Icon className="h-3.5 w-3.5" />
      {type}
    </Badge>
  );
}

export function SourceTypeBadge({ source }: { source: SourceKind }) {
  const Icon = source === "Recorded" ? Mic : source === "Uploaded" ? UploadCloud : FolderUp;
  const label = source === "ExternalUrl" ? "External URL" : source;
  return (
    <Badge toneKey={source}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </Badge>
  );
}

export function StatusBadge({ status }: { status?: TranslationStatus | null }) {
  const normalized = normalizeStatus(status);
  const Icon =
    normalized === "Completed"
      ? CheckCircle2
      : normalized === "Failed"
        ? XCircle
        : normalized === "Cancelled"
          ? Clock3
          : normalized === "Processing"
            ? Radio
            : Clock3;

  return (
    <Badge toneKey={normalized}>
      <Icon className="h-3.5 w-3.5" />
      {normalized}
    </Badge>
  );
}

export function JobBadges({ job }: { job: TranslationDto }) {
  return (
    <>
      <MediaTypeBadge type={getJobMediaKind(job)} />
      <SourceTypeBadge source={getJobSourceType(job)} />
      <StatusBadge status={job.status} />
    </>
  );
}
