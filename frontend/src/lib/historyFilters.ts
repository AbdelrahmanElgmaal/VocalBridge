import type { TranslationDto } from "../types/api";
import { getJobMediaKind, getJobMediaName, getJobSourceType } from "./mediaDashboard";
import { normalizeStatus } from "./status";

export type HistoryFilter =
  | "all"
  | "videos"
  | "audio"
  | "recordedAudio"
  | "uploadedAudio"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";
export type HistorySort = "newest" | "oldest";

export interface HistoryQuery {
  search: string;
  filter: HistoryFilter;
  sort: HistorySort;
}

function matchesSearch(job: TranslationDto, search: string) {
  const query = search.trim().toLowerCase();
  if (!query) return true;
  return getJobMediaName(job).toLowerCase().includes(query) || job.id.toLowerCase().includes(query);
}

function matchesFilter(job: TranslationDto, filter: HistoryFilter) {
  const mediaKind = getJobMediaKind(job);
  const sourceType = getJobSourceType(job);
  const status = normalizeStatus(job.status);

  switch (filter) {
    case "videos":
      return mediaKind === "Video";
    case "audio":
      return mediaKind === "Audio";
    case "recordedAudio":
      return mediaKind === "Audio" && sourceType === "Recorded";
    case "uploadedAudio":
      return mediaKind === "Audio" && sourceType === "Uploaded";
    case "processing":
      return status === "Processing";
    case "completed":
      return status === "Completed";
    case "failed":
      return status === "Failed";
    case "cancelled":
      return status === "Cancelled";
    default:
      return true;
  }
}

export function filterHistoryJobs(jobs: TranslationDto[], query: HistoryQuery) {
  const filtered = jobs.filter((job) => matchesSearch(job, query.search) && matchesFilter(job, query.filter));

  return [...filtered].sort((a, b) => {
    switch (query.sort) {
      case "oldest":
        return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
      default:
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    }
  });
}
