import { useState } from "react";
import { Download, ExternalLink, Play, RotateCcw, Square, Trash2 } from "lucide-react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useDeleteAudio, useAudio } from "../../hooks/useAudios";
import { useCancelTranslation, useRetryTranslation } from "../../hooks/useTranslations";
import { useDeleteVideo, useVideo } from "../../hooks/useVideos";
import { downloadFile } from "../../lib/media";
import { getJobMediaKind, getJobMediaName, getJobSourceType } from "../../lib/mediaDashboard";
import { isActiveStatus, isStatus, normalizeStatus } from "../../lib/status";
import { formatBytes, formatDate } from "../../lib/utils";
import type { CreateTranslationRequest, TranslationDto } from "../../types/api";
import { Button } from "../ui/Button";
import { JobBadges } from "../ui/MediaBadges";
import { useToast } from "../ui/Toast";
import { AudioPlayerModal } from "./AudioPlayerModal";
import { VideoPlayerModal } from "./VideoPlayerModal";

interface HistoryGridProps {
  jobs: TranslationDto[];
}

function voiceSummary(job: TranslationDto) {
  if (job.voiceCloning ?? true) return "Voice cloning";
  return [job.voiceGender, job.voiceAge, job.voicePitch, job.voiceStyle].filter(Boolean).join(" / ") || "Manual voice";
}

function formatDuration(seconds?: number | null) {
  if (!seconds) return "Not available";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

function retryPayload(job: TranslationDto): CreateTranslationRequest {
  const isAudio = getJobMediaKind(job) === "Audio";
  return {
    inputType: isAudio ? 1 : 0,
    ...(isAudio && job.audio?.id ? { audioId: job.audio.id } : {}),
    ...(!isAudio && job.video?.id ? { videoId: job.video.id } : {}),
    voiceCloning: job.voiceCloning ?? true,
    burnSubtitles: isAudio ? false : job.burnSubtitles ?? true,
    ...(!(job.voiceCloning ?? true)
      ? {
          voiceGender: job.voiceGender ?? undefined,
          voiceAge: job.voiceAge ?? undefined,
          voicePitch: job.voicePitch ?? undefined,
          voiceStyle: job.voiceStyle ?? undefined
        }
      : {})
  };
}

export function HistoryGrid({ jobs }: HistoryGridProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const [activeJob, setActiveJob] = useState<TranslationDto | undefined>();
  const activeKind = activeJob ? getJobMediaKind(activeJob) : "Video";
  const activeVideo = useVideo(activeKind === "Video" ? activeJob?.video?.id : undefined);
  const activeAudio = useAudio(activeKind === "Audio" ? activeJob?.audio?.id : undefined);
  const deleteVideo = useDeleteVideo();
  const deleteAudio = useDeleteAudio();
  const cancelTranslation = useCancelTranslation();
  const retryTranslation = useRetryTranslation();

  async function download(url: string | null | undefined, fileName: string, label: string) {
    if (!url) return;
    
    try {
      await downloadFile(url, fileName);
      toast({ tone: "success", title: "Download Ready", description: `${label} download has started.` });
    } catch (error) {
      toast({ tone: "error", title: "Download failed", description: error instanceof Error ? error.message : "Unable to download this media." });
    }
  }

  function getOriginalUrl(job: TranslationDto) {
    const isAudio = getJobMediaKind(job) === "Audio";
    return isAudio ? job.audio?.url : job.video?.url;
  }

  function getResultUrl(job: TranslationDto) {
    const isAudio = getJobMediaKind(job) === "Audio";
    return isAudio ? job.translatedAudioUrl : job.translatedVideoUrl;
  }

  async function retry(job: TranslationDto) {
    try {
      const nextJob = await retryTranslation.mutateAsync({ id: job.id, options: retryPayload(job) });
      toast({ tone: "success", title: "Retry Started", description: "A new dubbing job has been created." });
      navigate(`/translations/${nextJob.id}`);
    } catch (error) {
      toast({ tone: "error", title: "Retry Failed", description: error instanceof Error ? error.message : "Unable to retry this job." });
    }
  }

  function deleteMedia(job: TranslationDto) {
    const mediaName = getJobMediaName(job);
    if (!window.confirm(`Delete "${mediaName}" permanently?`)) return;
    const callbacks = {
      onSuccess: () => toast({ tone: "success", title: "Media Deleted", description: "Media and related jobs were removed." }),
      onError: (error: unknown) => toast({ tone: "error", title: "Delete Failed", description: error instanceof Error ? error.message : "Unable to delete this media." })
    };
    if (job.video?.id) deleteVideo.mutate(job.video.id, callbacks);
    if (job.audio?.id) deleteAudio.mutate(job.audio.id, callbacks);
  }

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        {jobs.map((job, index) => {
          const mediaKind = getJobMediaKind(job);
          const sourceType = getJobSourceType(job);
          const mediaName = getJobMediaName(job);
          const isAudio = mediaKind === "Audio";
          const canRetry = isStatus(job.status, "Failed") || isStatus(job.status, "Cancelled");
          const canCancel = isActiveStatus(job.status);
          const originalUrl = getOriginalUrl(job);
          const resultUrl = getResultUrl(job);
          const fileSize = isAudio ? job.audio?.fileSize : job.video?.fileSize;

          return (
            <motion.article
              key={job.id}
              className="glass rounded-xl p-5"
              initial={{ y: 14, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: Math.min(index * 0.03, 0.2) }}
            >
              <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="truncate text-base font-semibold text-white">{mediaName}</h3>
                    <p className="mt-1 text-xs text-slate-400">Job {job.id}</p>
                  </div>
                  <span className="shrink-0 rounded-full border border-zinc-700 px-2.5 py-1 text-xs font-semibold text-zinc-300">
                    {Math.round(job.progress)}%
                  </span>
                </div>

                <div className="flex flex-wrap gap-2">
                  <JobBadges job={job} />
                </div>

                <div className="grid gap-3 text-xs text-slate-400 sm:grid-cols-2">
                  <span>Created: {formatDate(job.createdAt)}</span>
                  <span>Completed: {formatDate(job.completedAt)}</span>
                  <span>Language: English to Arabic</span>
                  <span>Voice: {voiceSummary(job)}</span>
                  <span>Source: {sourceType}</span>
                  <span>Size: {formatBytes(fileSize)}</span>
                  {isAudio && <span>Duration: {formatDuration(job.audio?.durationSeconds)}</span>}
                </div>

                {job.errorMessage && normalizeStatus(job.status) === "Failed" && (
                  <p className="rounded-lg border border-rose-400/20 bg-rose-500/10 p-3 text-xs leading-5 text-rose-100">{job.errorMessage}</p>
                )}

                <div className="flex flex-wrap gap-2 border-t border-[var(--line)] pt-4">
                  <Button variant="secondary" onClick={() => setActiveJob(job)}>
                    <Play className="h-4 w-4" />
                    {isAudio ? "Listen" : "Preview"}
                  </Button>
                  <Button variant="secondary" onClick={() => navigate(`/translations/${job.id}`)}>
                    <ExternalLink className="h-4 w-4" />
                    View Details
                  </Button>
                  <Button variant="ghost" onClick={() => download(originalUrl, mediaName, "Original media")} disabled={!originalUrl}>
                    <Download className="h-4 w-4" />
                    Original
                  </Button>
                  <Button variant="ghost" onClick={() => download(resultUrl, mediaName, "Translated result")} disabled={!resultUrl}>
                    <Download className="h-4 w-4" />
                    Result
                  </Button>
                  {canRetry && (
                    <Button variant="secondary" loading={retryTranslation.isPending} onClick={() => retry(job)}>
                      <RotateCcw className="h-4 w-4" />
                      Retry
                    </Button>
                  )}
                  {canCancel && (
                    <Button variant="danger" loading={cancelTranslation.isPending} onClick={() => cancelTranslation.mutate(job.id)}>
                      <Square className="h-4 w-4" />
                      Cancel
                    </Button>
                  )}
                  <Button
                    variant="danger"
                    className="ml-auto"
                    loading={deleteVideo.isPending || deleteAudio.isPending}
                    onClick={() => deleteMedia(job)}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete Media
                  </Button>
                </div>
              </div>
            </motion.article>
          );
        })}
      </div>

      <VideoPlayerModal
        open={Boolean(activeJob && activeKind === "Video")}
        title={activeJob ? getJobMediaName(activeJob) : "Vocal Bridge Player"}
        url={activeJob?.translatedVideoUrl ?? activeVideo.data?.url ?? activeJob?.video?.url}
        onClose={() => setActiveJob(undefined)}
      />
      <AudioPlayerModal
        open={Boolean(activeJob && activeKind === "Audio")}
        title={activeJob ? getJobMediaName(activeJob) : "Vocal Bridge Audio"}
        url={activeJob?.translatedAudioUrl ?? activeAudio.data?.url ?? activeJob?.audio?.url}
        onClose={() => setActiveJob(undefined)}
      />
    </>
  );
}
