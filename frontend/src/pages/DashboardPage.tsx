import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  FileAudio,
  FileVideo,
  History,
  Layers3,
  Mic,
  RotateCcw,
  UploadCloud,
  XCircle
} from "lucide-react";
import { AudioPlayerModal } from "../components/history/AudioPlayerModal";
import { VideoPlayerModal } from "../components/history/VideoPlayerModal";
import { AppShell } from "../components/layout/AppShell";
import { DashboardChart } from "../components/dashboard/DashboardChart";
import { MetricCard } from "../components/dashboard/MetricCard";
import { QuickActionCard } from "../components/dashboard/QuickActionCard";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { MediaTypeBadge, SourceTypeBadge, StatusBadge } from "../components/ui/MediaBadges";
import { Skeleton } from "../components/ui/Skeleton";
import { useAudios, useDeleteAudio } from "../hooks/useAudios";
import { useTranslations } from "../hooks/useTranslations";
import { useDeleteVideo, useVideos } from "../hooks/useVideos";
import { useToast } from "../components/ui/Toast";
import { getApiError } from "../lib/api";
import { buildMediaItems, getDashboardStats, getJobMediaKind, getJobMediaName, getJobSourceType, getStatusCounts, type MediaItem } from "../lib/mediaDashboard";
import { isStatus } from "../lib/status";
import { formatDate } from "../lib/utils";

export function DashboardPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const videos = useVideos();
  const audios = useAudios();
  const translations = useTranslations(true);
  const deleteVideo = useDeleteVideo();
  const deleteAudio = useDeleteAudio();
  const [activeMedia, setActiveMedia] = useState<MediaItem | undefined>();

  const videoData = videos.data ?? [];
  const jobData = translations.data ?? [];
  const audioData = audios.data ?? [];

  const stats = useMemo(() => getDashboardStats(videoData, audioData, jobData), [audioData, jobData, videoData]);
  const recentMedia = useMemo(() => buildMediaItems(videoData, audioData, jobData).slice(0, 6), [audioData, jobData, videoData]);
  const recentActivity = useMemo(() => jobData.slice(0, 6), [jobData]);
  const failedJobs = useMemo(() => jobData.filter((job) => isStatus(job.status, "Failed")), [jobData]);
  
  const activeMediaUrl = useMemo(() => {
    if (!activeMedia) return undefined;
    const isCompleted = activeMedia.latestJob && isStatus(activeMedia.latestJob.status, "Completed");
    if (isCompleted) {
      if (activeMedia.kind === "Video" && activeMedia.latestJob?.translatedVideoUrl) return activeMedia.latestJob.translatedVideoUrl;
      if (activeMedia.kind === "Audio" && activeMedia.latestJob?.translatedAudioUrl) return activeMedia.latestJob.translatedAudioUrl;
    }
    return activeMedia.url;
  }, [activeMedia]);

  const loading = videos.isLoading || audios.isLoading || translations.isLoading;

  if (videos.isError || audios.isError || translations.isError) {
    return (
      <AppShell>
        <ErrorCard
          message={getApiError(videos.error ?? audios.error ?? translations.error)}
          onRetry={() => {
            videos.refetch();
            audios.refetch();
            translations.refetch();
          }}
        />
      </AppShell>
    );
  }

  function deleteMedia(media: MediaItem) {
    if (!window.confirm(`Delete "${media.fileName}" permanently?`)) return;
    const mutation = media.kind === "Video" ? deleteVideo : deleteAudio;
    mutation.mutate(media.id, {
      onSuccess: () => toast({ tone: "success", title: `${media.kind} Deleted`, description: "Media and related jobs were removed." }),
      onError: (error) => toast({ tone: "error", title: "Delete Failed", description: getApiError(error) })
    });
  }

  return (
    <AppShell>
      <div className="mb-10 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-electric">Media Dashboard</p>
          <h1 className="mt-2 text-3xl font-bold text-zinc-100 md:text-4xl">Workspace overview</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
            Monitor video and audio dubbing jobs from one production-ready media dashboard.
          </p>
        </div>
        <Button onClick={() => navigate("/translate")}>Create Dubbing</Button>
      </div>

      {loading ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-32 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <div className="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Media" value={stats.totalMedia} icon={<Layers3 className="h-5 w-5" />} />
            <MetricCard label="Total Videos" value={stats.totalVideos} icon={<FileVideo className="h-5 w-5" />} />
            <MetricCard label="Total Audio Files" value={stats.totalAudios} icon={<FileAudio className="h-5 w-5" />} tone="violet" />
            <MetricCard label="Total Translation Jobs" value={stats.totalJobs} icon={<BarChart3 className="h-5 w-5" />} tone="green" />
          </div>

          <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Processing Jobs" value={stats.processingJobs} icon={<Activity className="h-5 w-5" />} tone="violet" />
            <MetricCard label="Completed Jobs" value={stats.completedJobs} icon={<CheckCircle2 className="h-5 w-5" />} tone="green" />
            <MetricCard label="Failed Jobs" value={stats.failedJobs} icon={<XCircle className="h-5 w-5" />} tone="amber" />
            <MetricCard label="Success Rate" value={`${stats.successRate}%`} icon={<CheckCircle2 className="h-5 w-5" />} />
          </div>

          <section className="glass mb-6 rounded-xl p-5">
            <div className="mb-5 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-zinc-100">Quick Actions</h2>
                <p className="mt-1 text-sm text-zinc-400">Start common media workflows without leaving the dashboard.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <QuickActionCard
                title="Upload Video"
                description="Start a video dubbing job."
                icon={<FileVideo className="h-5 w-5" />}
                onClick={() => navigate("/translate", { state: { tab: "upload_video" } })}
              />
              <QuickActionCard
                title="Record Voice"
                description="Capture audio from your microphone."
                icon={<Mic className="h-5 w-5" />}
                onClick={() => navigate("/translate", { state: { tab: "audio", audioSource: "record" } })}
              />
              <QuickActionCard
                title="Upload Existing Audio"
                description="Dub an existing audio file."
                icon={<UploadCloud className="h-5 w-5" />}
                onClick={() => navigate("/translate", { state: { tab: "audio", audioSource: "upload" } })}
              />
              <QuickActionCard
                title="View History"
                description="Review and manage all jobs."
                icon={<History className="h-5 w-5" />}
                onClick={() => navigate("/history")}
              />
              {failedJobs.length > 0 && (
                <QuickActionCard
                  title="Retry Failed Jobs"
                  description={`${failedJobs.length} job${failedJobs.length === 1 ? "" : "s"} need attention.`}
                  icon={<RotateCcw className="h-5 w-5" />}
                  tone="danger"
                  onClick={() => navigate("/history", { state: { filter: "failed" } })}
                />
              )}
            </div>
          </section>

          <div className="grid min-w-0 gap-6 xl:grid-cols-[1fr_1fr]">
            <section className="glass min-w-0 rounded-xl p-5">
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-zinc-100">Recent Activity</h2>
                  <p className="mt-1 text-sm text-zinc-400">Latest video and audio translation jobs.</p>
                </div>
                <Button variant="secondary" onClick={() => navigate("/history")}>View All</Button>
              </div>

              {recentActivity.length ? (
                <div className="space-y-3">
                  {recentActivity.map((job) => (
                    <button
                      key={job.id}
                      onClick={() => navigate(`/translations/${job.id}`)}
                      className="w-full rounded-lg border border-zinc-800 bg-white/5 p-4 text-left transition hover:border-electric/40 hover:bg-electric/10 focus:outline-none focus:ring-2 focus:ring-electric/30"
                    >
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-zinc-100">{getJobMediaName(job)}</p>
                          <p className="mt-1 text-xs text-zinc-500">{formatDate(job.createdAt)}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <MediaTypeBadge type={getJobMediaKind(job)} />
                          <SourceTypeBadge source={getJobSourceType(job)} />
                          <StatusBadge status={job.status} />
                          <span className="rounded-full border border-zinc-700 px-2.5 py-1 text-xs font-semibold text-zinc-300">
                            {Math.round(job.progress)}%
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<Activity className="h-7 w-7" />}
                  title="No activity yet"
                  description="Create a video or audio dubbing job and recent activity will appear here."
                  actionLabel="Create Dubbing"
                  onAction={() => navigate("/translate")}
                />
              )}
            </section>

            <section className="glass min-w-0 rounded-xl p-5">
              <div className="mb-5">
                <h2 className="text-xl font-semibold text-zinc-100">Recent Media</h2>
                <p className="mt-1 text-sm text-zinc-400">Recently uploaded videos, recorded voices, and uploaded audio.</p>
              </div>

              {recentMedia.length ? (
                <div className="space-y-3">
                  {recentMedia.map((media) => (
                    <div key={`${media.kind}-${media.id}`} className="rounded-lg border border-zinc-800 bg-white/5 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-zinc-100">{media.fileName}</p>
                          <p className="mt-1 text-xs text-zinc-500">{formatDate(media.createdAt)}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <MediaTypeBadge type={media.kind} />
                          <SourceTypeBadge source={media.sourceType} />
                          {media.latestJob ? <StatusBadge status={media.latestJob.status} /> : <span className="text-xs text-zinc-500">No job yet</span>}
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--line)] pt-3">
                        <Button 
                          variant="secondary" 
                          className="h-9 px-3 text-xs" 
                          onClick={() => setActiveMedia(media)} 
                          disabled={!media.url && !(media.latestJob && isStatus(media.latestJob.status, "Completed") && (media.latestJob.translatedVideoUrl || media.latestJob.translatedAudioUrl))}
                        >
                          Preview
                        </Button>
                        <Button variant="secondary" className="h-9 px-3 text-xs" disabled={!media.latestJob} onClick={() => media.latestJob && navigate(`/translations/${media.latestJob.id}`)}>
                          View Job
                        </Button>
                        <Button
                          variant="danger"
                          className="ml-auto h-9 px-3 text-xs"
                          loading={deleteVideo.isPending || deleteAudio.isPending}
                          onClick={() => deleteMedia(media)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<Layers3 className="h-7 w-7" />}
                  title="No media yet"
                  description="Upload video, record voice, or upload audio to build your media workspace."
                  actionLabel="Create Dubbing"
                  onAction={() => navigate("/translate")}
                />
              )}
            </section>
          </div>

          {(stats.totalJobs > 0 || stats.totalAudios > 0) && (
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              {stats.totalJobs > 0 && (
                <DashboardChart title="Job Status Distribution" emptyText="Job status appears after processing starts." items={getStatusCounts(jobData)} />
              )}
              {stats.totalAudios > 0 && (
                <DashboardChart
                  title="Recorded vs Uploaded"
                  emptyText="Audio source distribution appears after audio is added."
                  items={[
                    { label: "Recorded", value: stats.recordedAudios },
                    { label: "Uploaded", value: stats.uploadedAudios }
                  ]}
                />
              )}
            </div>
          )}
        </>
      )}
      <VideoPlayerModal
        open={Boolean(activeMedia && activeMedia.kind === "Video")}
        title={activeMedia?.fileName ?? "Video Preview"}
        url={activeMediaUrl}
        onClose={() => setActiveMedia(undefined)}
      />
      <AudioPlayerModal
        open={Boolean(activeMedia && activeMedia.kind === "Audio")}
        title={activeMedia?.fileName ?? "Audio Preview"}
        url={activeMediaUrl}
        onClose={() => setActiveMedia(undefined)}
      />
    </AppShell>
  );
}
