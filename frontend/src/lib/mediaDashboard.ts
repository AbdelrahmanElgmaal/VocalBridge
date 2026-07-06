import type { AudioDto, InputType, TranslationDto, VideoDto } from "../types/api";
import { isActiveStatus, isStatus, normalizeStatus } from "./status";

export type MediaKind = "Video" | "Audio";
export type SourceKind = "Recorded" | "Uploaded" | "ExternalUrl" | "Unknown";

export interface MediaItem {
  id: string;
  fileName: string;
  kind: MediaKind;
  sourceType: SourceKind;
  createdAt: string;
  fileSize?: number | null;
  durationSeconds?: number | null;
  url?: string | null;
  latestJob?: TranslationDto;
}

export interface DashboardStats {
  totalMedia: number;
  totalVideos: number;
  totalAudios: number;
  totalJobs: number;
  processingJobs: number;
  completedJobs: number;
  failedJobs: number;
  successRate: number;
  recordedAudios: number;
  uploadedAudios: number;
}

export function normalizeInputType(inputType?: InputType | null): MediaKind {
  if (inputType === 1 || String(inputType).toLowerCase() === "audio") return "Audio";
  return "Video";
}

export function normalizeSourceType(sourceType?: string | null): SourceKind {
  const raw = String(sourceType ?? "").toLowerCase();
  if (raw === "recorded") return "Recorded";
  if (raw === "uploaded") return "Uploaded";
  if (raw === "externalurl" || raw === "external url" || raw === "url") return "ExternalUrl";
  return sourceType ? (sourceType as SourceKind) : "Unknown";
}

export function getJobMediaKind(job: TranslationDto): MediaKind {
  return normalizeInputType(job.inputType);
}

export function getJobMediaName(job: TranslationDto) {
  return job.video?.fileName || job.audio?.fileName || "Unknown media";
}

export function getJobSourceType(job: TranslationDto): SourceKind {
  return normalizeSourceType(job.audio?.sourceType ?? job.video?.sourceType);
}

export function getMediaId(job: TranslationDto) {
  return job.video?.id || job.audio?.id;
}

export function buildLatestJobMap(translations: TranslationDto[]) {
  const map = new Map<string, TranslationDto>();
  for (const job of translations) {
    const mediaId = getMediaId(job);
    if (!mediaId) continue;
    const current = map.get(mediaId);
    if (!current || new Date(job.createdAt).getTime() > new Date(current.createdAt).getTime()) {
      map.set(mediaId, job);
    }
  }
  return map;
}

export function buildMediaItems(videos: VideoDto[], audios: AudioDto[], translations: TranslationDto[]): MediaItem[] {
  const latestJobByMediaId = buildLatestJobMap(translations);

  return [
    ...videos.map((video) => ({
      id: video.id,
      fileName: video.fileName,
      kind: "Video" as const,
      sourceType: normalizeSourceType(video.sourceType),
      createdAt: video.uploadedAt,
      fileSize: video.fileSize,
      url: video.url,
      latestJob: latestJobByMediaId.get(video.id)
    })),
    ...audios.map((audio) => ({
      id: audio.id,
      fileName: audio.fileName,
      kind: "Audio" as const,
      sourceType: normalizeSourceType(audio.sourceType),
      createdAt: audio.createdAt,
      fileSize: audio.fileSize,
      durationSeconds: audio.durationSeconds,
      url: audio.url,
      latestJob: latestJobByMediaId.get(audio.id)
    }))
  ].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function getAudiosFromJobs(translations: TranslationDto[]): AudioDto[] {
  const audios = new Map<string, AudioDto>();
  for (const job of translations) {
    if (job.audio?.id && !audios.has(job.audio.id)) {
      audios.set(job.audio.id, job.audio);
    }
  }
  return [...audios.values()].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function getDashboardStats(videos: VideoDto[], audios: AudioDto[], translations: TranslationDto[]): DashboardStats {
  const completedJobs = translations.filter((job) => isStatus(job.status, "Completed")).length;
  const failedJobs = translations.filter((job) => isStatus(job.status, "Failed")).length;
  const terminalJobs = completedJobs + failedJobs + translations.filter((job) => isStatus(job.status, "Cancelled")).length;

  return {
    totalMedia: videos.length + audios.length,
    totalVideos: videos.length,
    totalAudios: audios.length,
    totalJobs: translations.length,
    processingJobs: translations.filter((job) => isActiveStatus(job.status)).length,
    completedJobs,
    failedJobs,
    successRate: terminalJobs ? Math.round((completedJobs / terminalJobs) * 100) : 0,
    recordedAudios: audios.filter((audio) => normalizeSourceType(audio.sourceType) === "Recorded").length,
    uploadedAudios: audios.filter((audio) => normalizeSourceType(audio.sourceType) === "Uploaded").length
  };
}

export function getStatusCounts(translations: TranslationDto[]) {
  return ["Queued", "Processing", "Completed", "Failed", "Cancelled"].map((status) => ({
    label: status,
    value: translations.filter((job) => normalizeStatus(job.status) === status).length
  }));
}
