import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  Clock,
  Copy,
  Download,
  Film,
  Mic,
  RefreshCcw,
  RotateCcw,
  Scissors,
  Square,
  Trash2,
  WandSparkles,
  Waves,
  XCircle
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { MediaPreview } from "../components/ui/MediaPreview";
import { Modal } from "../components/ui/Modal";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { useCancelTranslation, useRetryTranslation, useTranslation } from "../hooks/useTranslations";
import { useDeleteVideo, useVideo } from "../hooks/useVideos";
import { useAudio, useDeleteAudio } from "../hooks/useAudios";
import { getApiError } from "../lib/api";
import { downloadFile } from "../lib/media";
import { getJobMediaKind, getJobSourceType } from "../lib/mediaDashboard";
import { isActiveStatus, isStatus, normalizeStatus } from "../lib/status";
import { formatDate } from "../lib/utils";

const genderOptions = ["male", "female"];
const ageOptions = ["child", "teenager", "young adult", "middle-aged", "elderly"];
const pitchOptions = ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"];
const styleOptions = ["natural", "whisper"];

const videoStages = [
  { key: "extract_audio", title: "Extract Audio", description: "Separate audio track from uploaded video.", icon: Scissors, threshold: 10 },
  { key: "speech_recognition", title: "Speech Recognition", description: "Convert English speech into text using Whisper.", icon: Mic, threshold: 30 },
  { key: "translate", title: "Translate", description: "Translate English transcript into Arabic.", icon: WandSparkles, threshold: 50 },
  { key: "voice_generation", title: "Voice Generation", description: "Generate Arabic speech using AI voice synthesis.", icon: Waves, threshold: 75 },
  { key: "merge_video", title: "Merge Video", description: "Replace original speech with generated Arabic speech.", icon: RefreshCcw, threshold: 95 },
  { key: "completed", title: "Completed", description: "Translation finished successfully.", icon: CheckCircle2, threshold: 100 }
];

const audioStages = [
  { key: "speech_recognition", title: "Speech Recognition", description: "Convert English audio into text using Whisper.", icon: Mic, threshold: 30 },
  { key: "translate", title: "Translate", description: "Translate English transcript into Arabic.", icon: WandSparkles, threshold: 50 },
  { key: "voice_generation", title: "Voice Generation", description: "Generate Arabic speech using AI voice synthesis.", icon: Waves, threshold: 75 },
  { key: "assemble_audio", title: "Assemble Audio", description: "Prepare the final dubbed Arabic audio track.", icon: RefreshCcw, threshold: 95 },
  { key: "completed", title: "Completed", description: "Audio dubbing finished successfully.", icon: CheckCircle2, threshold: 100 }
];

function stageState(stages: typeof videoStages, progress: number, currentStage: string | null | undefined, index: number, failed: boolean) {
  const currentIndex = currentStage ? stages.findIndex((stage) => stage.key === currentStage) : -1;
  if (failed) {
    const fallbackIndex = stages.findIndex((stage) => progress < stage.threshold);
    const failedIndex = currentIndex >= 0
      ? currentIndex
      : fallbackIndex === -1 ? stages.length - 1 : Math.max(0, fallbackIndex);
    if (index < failedIndex) return "Completed";
    return index === failedIndex ? "Failed" : "Pending";
  }
  if (currentIndex >= 0) {
    if (index < currentIndex) return "Completed";
    if (index === currentIndex) return currentStage === "completed" ? "Completed" : "Current";
    return "Pending";
  }
  if (progress >= stages[index].threshold) return "Completed";
  if (index === 0 || progress >= stages[index - 1].threshold) return "Current";
  return "Pending";
}

function statusPhrase(status: string, progress: number) {
  if (status === "Completed") return "Completed";
  if (status === "Failed") return "Dubbing Failed";
  if (status === "Cancelled") return "Cancelled";
  if (status === "Queued") return "Waiting...";
  if (progress > 85) return "Almost Finished...";
  if (progress > 10) return "Processing...";
  return "Preparing AI Job...";
}

function voiceSummary(job: NonNullable<ReturnType<typeof useTranslation>["data"]>) {
  if (job.voiceCloning ?? true) return "Voice cloning";
  return [job.voiceGender, job.voiceAge, job.voicePitch, job.voiceStyle].filter(Boolean).join(" / ") || "Manual voice";
}

export function TranslationDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const lastStatus = useRef<string>("");
  const translation = useTranslation(id, true);
  const job = translation.data;
  
  const isAudio = job?.inputType === 1 || job?.inputType === "Audio" || job?.inputType === "audio";
  const video = useVideo(isAudio ? undefined : job?.video?.id);
  const audio = useAudio(isAudio ? job?.audio?.id : undefined);
  const cancel = useCancelTranslation();
  const retry = useRetryTranslation();
  const deleteVideo = useDeleteVideo();
  const deleteAudio = useDeleteAudio();

  const status = normalizeStatus(job?.status);
  const progress = Math.round(job?.progress ?? 0);
  const currentStage = job?.currentStage ?? null;
  const stages = isAudio ? audioStages : videoStages;
  const active = isActiveStatus(job?.status);
  const failed = isStatus(job?.status, "Failed");
  const cancelled = isStatus(job?.status, "Cancelled");
  const canRetry = failed || cancelled;

  const [retryModalOpen, setRetryModalOpen] = useState(false);
  const [voiceCloning, setVoiceCloning] = useState(true);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [voiceGender, setVoiceGender] = useState("male");
  const [voiceAge, setVoiceAge] = useState("young adult");
  const [voicePitch, setVoicePitch] = useState("moderate pitch");
  const [voiceStyle, setVoiceStyle] = useState("natural");

  function openRetryModal() {
    if (job) {
      setVoiceCloning(job.voiceCloning ?? true);
      setBurnSubtitles(job.burnSubtitles ?? true);
      setVoiceGender(job.voiceGender ?? "male");
      setVoiceAge(job.voiceAge ?? "young adult");
      setVoicePitch(job.voicePitch ?? "moderate pitch");
      setVoiceStyle(job.voiceStyle ?? "natural");
      setRetryModalOpen(true);
    }
  }

  async function handleRetrySubmit() {
    if (!job) return;

    if (!voiceCloning && (!voiceGender || !voiceAge || !voicePitch || !voiceStyle)) {
      toast({ tone: "error", title: "Missing Voice Settings", description: "Please configure all voice options when Voice Cloning is disabled." });
      return;
    }

    const options = {
      inputType: isAudio ? 1 : 0,
      ...(isAudio && job.audio?.id ? { audioId: job.audio.id } : {}),
      ...(!isAudio && job.video?.id ? { videoId: job.video.id } : {}),
      voiceCloning,
      burnSubtitles: isAudio ? false : burnSubtitles,
      ...(!voiceCloning ? { voiceGender, voiceAge, voicePitch, voiceStyle } : {})
    };

    try {
      const newJob = await retry.mutateAsync({ id: job.id, options });
      toast({ tone: "success", title: "Retry Started", description: "A new dubbing job has been created." });
      setRetryModalOpen(false);
      navigate(`/translations/${newJob.id}`);
    } catch (error) {
      toast({ tone: "error", title: "Retry Failed", description: getApiError(error) });
    }
  }

  useEffect(() => {
    if (!job) return;
    const normalized = normalizeStatus(job.status);
    if (lastStatus.current === normalized) return;
    lastStatus.current = normalized;
    if (normalized === "Completed") toast({ tone: "success", title: "Dubbing Completed", description: "Download and online preview are ready." });
    if (normalized === "Failed") toast({ tone: "error", title: "Dubbing Failed", description: job.errorMessage ?? "The AI service could not complete this job." });
    if (normalized === "Cancelled") toast({ tone: "info", title: "Cancelled", description: "This job is no longer processing." });
  }, [job, toast]);


  if (translation.isLoading) {
    return (
      <AppShell>
        <div className="space-y-5">
          <Skeleton className="h-12 w-72" />
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </AppShell>
    );
  }

  if (translation.isError || !job) {
    return (
      <AppShell>
        <ErrorCard message={getApiError(translation.error) || "Translation job was not found."} onRetry={() => translation.refetch()} />
      </AppShell>
    );
  }

  async function copyLink() {
    const url = isAudio ? job?.translatedAudioUrl : job?.translatedVideoUrl;
    if (!url) return;
    await navigator.clipboard.writeText(url);
    toast({ tone: "success", title: "Link copied", description: `Translated ${isAudio ? "audio" : "video"} link copied.` });
  }

  async function downloadResult() {
    const playUrl = isAudio ? job?.translatedAudioUrl : job?.translatedVideoUrl;
    if (!playUrl) return;
    try {
      const fileName = isAudio 
        ? job?.audio?.fileName || "translated-audio.wav"
        : job?.video?.fileName || "translated-video.mp4";
      await downloadFile(playUrl, fileName);
      toast({ tone: "success", title: "Download Ready", description: `Your browser is downloading the translated ${isAudio ? "audio" : "video"}.` });
    } catch (error) {
      toast({ tone: "error", title: "Download failed", description: error instanceof Error ? error.message : `Unable to download this ${isAudio ? "audio" : "video"}.` });
    }
  }

  function deleteMedia() {
    if (!job) return;
    const mediaName = isAudio ? job.audio?.fileName : job.video?.fileName;
    if (!mediaName || !window.confirm(`Delete "${mediaName}" permanently?`)) return;

    const callbacks = {
      onSuccess: () => {
        toast({ tone: "success", title: `${isAudio ? "Audio" : "Video"} Deleted`, description: "Media and related jobs were removed." });
        navigate("/history");
      },
      onError: (error: unknown) => {
        toast({ tone: "error", title: "Delete Failed", description: getApiError(error) });
      }
    };

    if (isAudio && job.audio?.id) deleteAudio.mutate(job.audio.id, callbacks);
    if (!isAudio && job.video?.id) deleteVideo.mutate(job.video.id, callbacks);
  }

  return (
    <AppShell>
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-electric">Dubbing Details</p>
          <h1 className="mt-2 text-3xl font-bold text-[var(--text)] md:text-4xl">{isAudio ? job.audio?.fileName : job.video?.fileName}</h1>
          <p className="mt-3 text-sm text-[var(--muted)]">{statusPhrase(status, progress)}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {active && (
            <Button
              variant="danger"
              loading={cancel.isPending}
              onClick={async () => {
                await cancel.mutateAsync(job.id);
                toast({ tone: "info", title: "Cancelled", description: "The translation job was cancelled." });
              }}
            >
              <Square className="h-4 w-4" />
              Cancel
            </Button>
          )}
          {canRetry && (
            <Button
              variant="primary"
              onClick={openRetryModal}
            >
              <RotateCcw className="h-4 w-4" />
              Retry Dubbing
            </Button>
          )}
          <Button variant="secondary" onClick={() => navigate("/dashboard")}>Dashboard</Button>
          <Button variant="secondary" onClick={() => navigate("/history")}>History</Button>
          <Button
            variant="danger"
            loading={deleteVideo.isPending || deleteAudio.isPending}
            onClick={deleteMedia}
          >
            <Trash2 className="h-4 w-4" />
            Delete {isAudio ? "Audio" : "Video"}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="glass rounded-xl p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--text)]">{isAudio ? "Audio Preview" : "Video Preview"}</h2>
            <Badge>{status}</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-semibold text-[var(--muted)]">Original {isAudio ? "Audio" : "Video"}</p>
              {isAudio && audio.data?.url ? (
                <div className="flex h-32 w-full items-center justify-center rounded-xl border border-[var(--line)] bg-zinc-900/50 p-4">
                  <audio src={audio.data.url} controls className="w-full" />
                </div>
              ) : !isAudio && video.data?.url ? (
                <MediaPreview url={video.data.url} title="Original video" />
              ) : (
                <div className="flex aspect-video items-center justify-center rounded-xl bg-black/60 text-sm text-white/50">Original preview unavailable</div>
              )}
            </div>
            <div>
              <p className="mb-2 text-sm font-semibold text-[var(--muted)]">Translated {isAudio ? "Audio" : "Video"}</p>
              {isAudio && job.translatedAudioUrl ? (
                <div className="flex h-32 w-full items-center justify-center rounded-xl border border-[var(--line)] bg-zinc-900/50 p-4">
                  <audio src={job.translatedAudioUrl} controls className="w-full" />
                </div>
              ) : !isAudio && job.translatedVideoUrl ? (
                <MediaPreview url={job.translatedVideoUrl} title="Translated video" />
              ) : (
                <div className="flex aspect-video items-center justify-center rounded-xl bg-black/60 text-sm text-white/50">Result appears when complete</div>
              )}
            </div>
          </div>

          <div className="mt-6">
            <div className="mb-2 flex items-center justify-between text-sm text-[var(--muted)]">
              <span>Overall Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-white/10">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-electric to-violet"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(progress, 100)}%` }}
                transition={{ duration: 0.6 }}
              />
            </div>
          </div>
        </section>

        <section className="glass rounded-xl p-5">
          <h2 className="text-lg font-semibold text-[var(--text)]">Job Information</h2>
          <div className="mt-5 grid gap-3 text-sm">
            {[
              ["Job ID", job.id],
              ["Created Time", formatDate(job.createdAt)],
              ["Completed Time", formatDate(job.completedAt)],
              ["Media Type", getJobMediaKind(job)],
              ["Source Type", getJobSourceType(job)],
              ["Current Status", status],
              ["Current Stage", currentStage?.replace(/_/g, " ") ?? "Waiting"],
              ["Progress", `${progress}%`],
              ["Voice Settings", voiceSummary(job)]
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-lg border border-[var(--line)] bg-white/5 px-4 py-3">
                <span className="text-[var(--muted)]">{label}</span>
                <span className="max-w-[14rem] truncate text-right font-semibold text-[var(--text)]">{value}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="glass mt-6 rounded-xl p-5">
        <h2 className="text-lg font-semibold text-[var(--text)]">AI Pipeline Timeline</h2>
        <div className="mt-6 space-y-4">
          {stages.map((stage, index) => {
            const state = stageState(stages, progress, currentStage, index, failed);
            const Icon = state === "Failed" ? XCircle : stage.icon;
            return (
              <motion.div
                key={stage.title}
                className={`relative rounded-xl border p-4 ${
                  state === "Current"
                    ? "border-electric/45 bg-electric/10 shadow-glow"
                    : state === "Completed"
                      ? "border-emerald-400/25 bg-emerald-400/10"
                      : state === "Failed"
                        ? "border-rose-400/30 bg-rose-500/10"
                        : "border-[var(--line)] bg-white/5"
                }`}
                animate={state === "Current" ? { scale: [1, 1.01, 1] } : { scale: 1 }}
                transition={{ repeat: state === "Current" ? Infinity : 0, duration: 1.8 }}
              >
                <div className="flex gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10 text-electric">
                    <Icon className="h-6 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="font-semibold text-[var(--text)]">{stage.title}</h3>
                      <Badge>{state}</Badge>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{stage.description}</p>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </section>

      {(job.transcript || job.translatedText) && (
        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          {job.transcript && (
            <div className="glass rounded-xl p-5">
              <h2 className="text-lg font-semibold text-[var(--text)]">Transcription</h2>
              <pre className="mt-4 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl border border-[var(--line)] bg-black/45 p-4 font-mono text-sm leading-6 text-zinc-200">{job.transcript}</pre>
            </div>
          )}

          {job.translatedText && (
            <div className="glass rounded-xl p-5">
              <h2 className="text-lg font-semibold text-[var(--text)]">Arabic Translation</h2>
              <pre
                dir="rtl"
                className="mt-4 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl border border-[var(--line)] bg-black/45 p-4 text-right font-[Tahoma] text-base leading-8 text-zinc-100"
              >{job.translatedText}</pre>
            </div>
          )}
        </section>
      )}

      <section className="glass mt-6 rounded-xl p-5">
        <h2 className="text-lg font-semibold text-[var(--text)]">Result</h2>
        {isStatus(job.status, "Completed") && (isAudio ? job.translatedAudioUrl : job.translatedVideoUrl) ? (
          <div className="mt-5">
            <div className="mb-6 flex flex-col items-center rounded-xl border border-emerald-400/25 bg-emerald-400/10 px-6 py-8 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-400/20">
                <CheckCircle2 className="h-8 w-8 text-emerald-300" />
              </div>
              <h3 className="mt-4 text-xl font-bold text-[var(--text)]">Dubbing Completed Successfully</h3>
              <p className="mt-2 max-w-md text-sm text-[var(--muted)]">Your {isAudio ? "audio" : "video"} has been dubbed from English to Arabic and is ready for download or online viewing.</p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button onClick={downloadResult}>
                <Download className="h-4 w-4" />
                Download {isAudio ? "Audio" : "Video"}
              </Button>
              <Button variant="secondary" onClick={() => window.open(isAudio ? job.translatedAudioUrl! : job.translatedVideoUrl!, "_blank")}>
                {isAudio ? "Listen" : "Preview"}
              </Button>
              <Button variant="ghost" onClick={copyLink}>
                <Copy className="h-4 w-4" />
                Copy Link
              </Button>
              <Button variant="secondary" onClick={() => navigate("/translate")}>
                <Film className="h-4 w-4" />
                Dub Another {isAudio ? "Audio" : "Video"}
              </Button>
              <Button variant="ghost" onClick={() => navigate("/dashboard")}>Back to Dashboard</Button>
            </div>
          </div>
        ) : (
          <EmptyState
            icon={<Clock className="h-7 w-7" />}
            title={failed ? "Result unavailable" : "Result is not ready yet"}
            description={failed ? job.errorMessage ?? `The AI job failed before producing dubbed ${isAudio ? "audio" : "video"}.` : `The dubbed ${isAudio ? "audio" : "video"} and download actions will appear automatically when processing completes.`}
          />
        )}
      </section>

      <Modal open={retryModalOpen} title="Retry Job Settings" onClose={() => setRetryModalOpen(false)}>
        <div className="space-y-4">
          <p className="text-sm text-[var(--muted)]">Review and adjust the voice settings for this retry.</p>
          
          <label className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--line)] bg-white/5 px-4 py-3 transition hover:bg-white/[0.08]">
            <div>
              <p className="text-sm font-semibold text-[var(--text)]">Enable Voice Cloning</p>
              <p className="mt-0.5 text-xs text-[var(--muted)]">Clone the original speaker's voice for dubbing</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={voiceCloning}
              onClick={() => setVoiceCloning(!voiceCloning)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                voiceCloning ? "bg-electric" : "bg-zinc-600"
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${voiceCloning ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </label>

          {/* Burn Subtitles Toggle */}
          {!isAudio && (
            <label className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--line)] bg-white/5 px-4 py-3 transition hover:bg-white/[0.08]">
              <div>
                <p className="text-sm font-semibold text-[var(--text)]">Burn Subtitles</p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">Embed translated subtitles into the output video</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={burnSubtitles}
                onClick={() => setBurnSubtitles(!burnSubtitles)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                  burnSubtitles ? "bg-electric" : "bg-zinc-600"
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${burnSubtitles ? "translate-x-6" : "translate-x-1"}`} />
              </button>
            </label>
          )}

          <AnimatePresence>
            {!voiceCloning && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: "easeInOut" }}
                className="overflow-hidden"
              >
                <div className="mt-2 space-y-4 border-t border-[var(--line)] pt-4">
                  <p className="text-sm font-semibold text-[var(--muted)]">Manual Voice Configuration</p>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-[var(--muted)]">Gender</label>
                      <select
                        value={voiceGender}
                        onChange={(e) => setVoiceGender(e.target.value)}
                        className="h-10 w-full rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                      >
                        {genderOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt.charAt(0).toUpperCase() + opt.slice(1)}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-[var(--muted)]">Age</label>
                      <select
                        value={voiceAge}
                        onChange={(e) => setVoiceAge(e.target.value)}
                        className="h-10 w-full rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                      >
                        {ageOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt.replace(/\b\w/g, l => l.toUpperCase())}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-[var(--muted)]">Pitch</label>
                      <select
                        value={voicePitch}
                        onChange={(e) => setVoicePitch(e.target.value)}
                        className="h-10 w-full rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                      >
                        {pitchOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt.replace(/\b\w/g, l => l.toUpperCase())}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-[var(--muted)]">Style</label>
                      <select
                        value={voiceStyle}
                        onChange={(e) => setVoiceStyle(e.target.value)}
                        className="h-10 w-full rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                      >
                        {styleOptions.map((opt) => (
                          <option key={opt} value={opt}>{opt.charAt(0).toUpperCase() + opt.slice(1)}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-6 flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setRetryModalOpen(false)} disabled={retry.isPending}>Cancel</Button>
            <Button variant="primary" loading={retry.isPending} onClick={handleRetrySubmit}>
              Start Retry
            </Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
}
