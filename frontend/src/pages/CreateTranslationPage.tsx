import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Download, Link2, Mic, PlayCircle, Square, Trash2, UploadCloud, Video, FileAudio } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { MediaPreview } from "../components/ui/MediaPreview";
import { useToast } from "../components/ui/Toast";
import { useCreateTranslation } from "../hooks/useTranslations";
import { useUploadVideo } from "../hooks/useVideos";
import { useUploadAudio } from "../hooks/useAudios";
import { getApiError } from "../lib/api";
import { isDirectVideoUrl } from "../lib/media";
import { formatBytes } from "../lib/utils";

const maxVideoFileSize = 500 * 1024 * 1024;
const maxAudioFileSize = 10 * 1024 * 1024; // 10 MB

const supportedVideo = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv"];
const supportedAudio = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm"];

const genderOptions = ["male", "female"];
const ageOptions = ["child", "teenager", "young adult", "middle-aged", "elderly"];
const pitchOptions = ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"];
const styleOptions = ["natural", "whisper"];

export function CreateTranslationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  
  const routeState = location.state as { tab?: "upload_video" | "audio" | "url"; audioSource?: "record" | "upload" } | null;
  const [tab, setTab] = useState<"upload_video" | "audio" | "url">(routeState?.tab ?? "upload_video");
  const [audioSource, setAudioSource] = useState<"record" | "upload">(routeState?.audioSource ?? "record");

  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  const uploadVideo = useUploadVideo(setUploadProgress);
  const uploadAudio = useUploadAudio(setUploadProgress);
  const createTranslation = useCreateTranslation();

  // Voice settings state
  const [voiceCloning, setVoiceCloning] = useState(true);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [enableLipsync, setEnableLipsync] = useState(false);
  const [voiceGender, setVoiceGender] = useState("male");
  const [voiceAge, setVoiceAge] = useState("young adult");
  const [voicePitch, setVoicePitch] = useState("moderate pitch");
  const [voiceStyle, setVoiceStyle] = useState("natural");

  // Recording states
  const [recordingStatus, setRecordingStatus] = useState<"idle" | "recording" | "ready" | "unsupported">("idle");
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
  const urlIsValid = !videoUrl || /^https?:\/\/[^\s]+$/i.test(videoUrl);
  
  const fileError = file ? (
    tab === "upload_video" && file.size > maxVideoFileSize ? "File is larger than 500 MB." :
    tab === "audio" && file.size > maxAudioFileSize ? "File is larger than 10 MB." : ""
  ) : "";
  
  const extensionError = file ? (
    tab === "upload_video" && !supportedVideo.some((extension) => file.name.toLowerCase().endsWith(extension)) ? "Unsupported video format." :
    tab === "audio" && audioSource === "upload" && !supportedAudio.some((extension) => file.name.toLowerCase().endsWith(extension)) ? "Unsupported audio format." : ""
  ) : "";

  // ── Recording Logic ──

  // Check support on mount
  useEffect(() => {
    if (!window.MediaRecorder) {
      setRecordingStatus("unsupported");
      setAudioSource("upload");
    }
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (recordingStatus === "recording") {
      interval = setInterval(() => {
        setRecordingTime(t => {
          if (t >= 59) {
            stopRecording();
            toast({ tone: "info", title: "Recording Stopped", description: "Maximum recording time is 60 seconds." });
            return 60;
          }
          return t + 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [recordingStatus]);

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      stopMediaTracks();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function stopMediaTracks() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      streamRef.current = null;
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType || "audio/webm" });
        const elapsedSeconds = (Date.now() - startTimeRef.current) / 1000;
        
        if (elapsedSeconds < 1) {
          toast({ tone: "error", title: "Recording too short", description: "Please record for at least 1 second." });
          discardRecording();
          return;
        }
        const ext = blob.type.includes("ogg") ? ".ogg" : ".webm";
        const uuid = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();
        const newFile = new File([blob], `voice_${uuid}${ext}`, { type: blob.type });
        setFile(newFile);
        setRecordingStatus("ready");
      };

      startTimeRef.current = Date.now();
      mediaRecorder.start();
      setRecordingStatus("recording");
      setRecordingTime(0);
    } catch (err: any) {
      const errorName = err?.name || "UnknownError";
      if (errorName === "NotAllowedError") {
        toast({ tone: "error", title: "Microphone Access Denied", description: "Please allow microphone permissions to record audio." });
      } else if (errorName === "NotFoundError") {
        toast({ tone: "error", title: "Microphone Not Found", description: "No microphone detected on this device." });
      } else {
        toast({ tone: "error", title: "Recording Error", description: err?.message || "Unable to access microphone." });
      }
    }
  }

  function stopRecording() {
    stopMediaTracks();
  }

  function discardRecording() {
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setRecordingStatus("idle");
    setRecordingTime(0);
    stopMediaTracks();
  }

  // ── Tab Logic ──
  function switchTab(nextTab: "upload_video" | "audio" | "url") {
    if (nextTab === tab) return;

    // Reset everything
    discardRecording();
    setUploadProgress(0);
    setDragging(false);
    if (inputRef.current) inputRef.current.value = "";
    if (nextTab !== "url") setVideoUrl("");

    setTab(nextTab);
  }

  function switchAudioSource(source: "record" | "upload") {
    if (source === audioSource) return;
    discardRecording();
    setUploadProgress(0);
    setDragging(false);
    if (inputRef.current) inputRef.current.value = "";
    setAudioSource(source);
  }

  function selectFile(nextFile: File) {
    setFile(nextFile);
    setUploadProgress(0);
  }

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0];
    if (nextFile) selectFile(nextFile);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const nextFile = event.dataTransfer.files?.[0];
    if (nextFile) selectFile(nextFile);
  }

  function downloadOriginalFromUrl() {
    if (!videoUrl || !urlIsValid) return;

    if (!isDirectVideoUrl(videoUrl)) {
      toast({
        tone: "info",
        title: "External download unavailable",
        description: "Direct download for external platform links is disabled. You can download the fully dubbed video once the pipeline completes."
      });
      return;
    }

    try {
      const parsed = new URL(videoUrl);
      const filename = parsed.pathname.split("/").filter(Boolean).pop() || "vocal-bridge-original-video.mp4";
      const anchor = document.createElement("a");
      anchor.href = videoUrl;
      anchor.download = filename;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      toast({ tone: "success", title: "Download Ready", description: "Your browser is downloading the original video." });
    } catch {
      window.open(videoUrl, "_blank", "noopener,noreferrer");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();

    // Validate manual voice fields when cloning is OFF
    if (!voiceCloning && (!voiceGender || !voiceAge || !voicePitch || !voiceStyle)) {
      toast({ tone: "error", title: "Missing Voice Settings", description: "Please configure all voice options when Voice Cloning is disabled." });
      return;
    }

    const voiceOptions = {
      voiceCloning,
      burnSubtitles,
      enableLipsync: tab === "audio" ? false : enableLipsync,
      ...(!voiceCloning ? { voiceGender, voiceAge, voicePitch, voiceStyle } : {}),
    };

    try {
      if (tab === "upload_video") {
        if (!file || fileError || extensionError) return;
        toast({ tone: "info", title: "Uploading...", description: "Sending your video to secure storage." });
        const uploaded = await uploadVideo.mutateAsync(file);
        toast({ tone: "success", title: "Upload Complete", description: "Preparing AI job..." });
        const translation = await createTranslation.mutateAsync({ videoId: uploaded.id, inputType: 0, ...voiceOptions });
        toast({ tone: "success", title: "Dubbing Started", description: "AI processing has begun." });
        navigate(`/translations/${translation.id}`);
        return;
      }
      
      if (tab === "audio") {
        if (!file || fileError || extensionError) return;
        if (audioSource === "record" && recordingStatus !== "ready") return;
        
        toast({ tone: "info", title: "Uploading...", description: "Sending your audio to secure storage." });
        // We pass the sourceType "Recorded" vs "Uploaded" based on user's selected tab toggle
        const uploaded = await uploadAudio.mutateAsync({ file, sourceType: audioSource === "record" ? "Recorded" : "Uploaded" });
        toast({ tone: "success", title: "Upload Complete", description: "Preparing AI job..." });
        const translation = await createTranslation.mutateAsync({ audioId: uploaded.id, inputType: 1, ...voiceOptions, burnSubtitles: false });
        toast({ tone: "success", title: "Dubbing Started", description: "AI processing has begun." });
        navigate(`/translations/${translation.id}`);
        return;
      }

      if (!videoUrl || !urlIsValid) return;
      toast({ tone: "info", title: "Preparing AI Job...", description: "Submitting external video URL." });
      const translation = await createTranslation.mutateAsync({ videoUrl, inputType: 0, ...voiceOptions });
      toast({ tone: "success", title: "Dubbing Started", description: "AI processing has begun." });
      navigate(`/translations/${translation.id}`);
    } catch (error) {
      toast({ tone: "error", title: "Dubbing Failed", description: getApiError(error) });
    }
  }

  const busy = uploadVideo.isPending || uploadAudio.isPending || createTranslation.isPending;

  function formatTime(seconds: number) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  return (
    <AppShell>
      <div className="mb-8">
        <p className="text-sm uppercase tracking-[0.24em] text-electric">Create Dubbing</p>
        <h1 className="mt-2 text-3xl font-bold text-[var(--text)] md:text-4xl">Start a new English to Arabic dub</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">Upload a local video, paste a URL, or provide audio to start a secure AI dubbing job.</p>
      </div>

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <section className="glass rounded-xl p-5">
            <div className="grid grid-cols-3 rounded-lg bg-white/[0.06] p-1">
              {[
                { id: "upload_video", label: "Upload Video", icon: UploadCloud },
                { id: "audio", label: "Dub Audio", icon: Mic },
                { id: "url", label: "Dub from URL", icon: Link2 }
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => switchTab(item.id as "upload_video" | "audio" | "url")}
                  className={`flex items-center justify-center gap-2 rounded-md px-3 py-3 text-sm font-semibold transition ${
                    tab === item.id ? "bg-electric text-ink shadow-glow" : "text-[var(--muted)] hover:text-[var(--text)]"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              ))}
            </div>

            {tab === "upload_video" && (
              <div className="mt-5 space-y-5">
                <input ref={inputRef} type="file" accept="video/*" className="hidden" onChange={onFileInput} />
                <div
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  className={`rounded-xl border border-dashed p-8 text-center transition ${
                    dragging ? "border-electric bg-electric/10" : "border-[var(--line)] bg-white/5"
                  }`}
                >
                  <UploadCloud className="mx-auto h-10 w-10 text-electric" />
                  <h3 className="mt-4 text-lg font-semibold text-[var(--text)]">Drag and drop your video</h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">Supported: {supportedVideo.join(", ")}. Max size: 500 MB.</p>
                  <Button type="button" variant="secondary" className="mt-5" onClick={() => inputRef.current?.click()}>
                    Browse file
                  </Button>
                </div>

                {file && (
                  <div className="rounded-xl border border-[var(--line)] bg-white/5 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[var(--text)]">{file.name}</p>
                        <p className="mt-1 text-xs text-[var(--muted)]">{formatBytes(file.size)}</p>
                      </div>
                      <Button type="button" variant="ghost" className="h-9 w-9 px-0" onClick={() => setFile(null)} aria-label="Remove file">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    {(fileError || extensionError) && <p className="mt-3 text-sm text-rose-300">{fileError || extensionError}</p>}
                    {busy && (
                      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                        <div className="h-full rounded-full bg-electric transition-all" style={{ width: `${uploadProgress}%` }} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {tab === "audio" && (
              <div className="mt-5 space-y-5">
                {/* Audio Source Selector */}
                <div className="flex items-center gap-4 rounded-lg bg-white/[0.04] p-1 border border-white/[0.05]">
                  <button
                    type="button"
                    onClick={() => switchAudioSource("record")}
                    disabled={recordingStatus === "unsupported"}
                    className={`flex-1 flex items-center justify-center gap-2 rounded-md py-2.5 text-sm font-medium transition ${
                      audioSource === "record" ? "bg-white/10 text-white shadow-sm" : "text-slate-400 hover:text-white"
                    } ${recordingStatus === "unsupported" ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    <div className={`h-2.5 w-2.5 rounded-full border border-current ${audioSource === "record" ? "bg-electric border-electric" : ""}`} />
                    Record Voice
                  </button>
                  <button
                    type="button"
                    onClick={() => switchAudioSource("upload")}
                    className={`flex-1 flex items-center justify-center gap-2 rounded-md py-2.5 text-sm font-medium transition ${
                      audioSource === "upload" ? "bg-white/10 text-white shadow-sm" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <div className={`h-2.5 w-2.5 rounded-full border border-current ${audioSource === "upload" ? "bg-electric border-electric" : ""}`} />
                    Upload Existing Audio
                  </button>
                </div>

                {audioSource === "upload" && (
                  <div className="space-y-5">
                    <input ref={inputRef} type="file" accept="audio/*" className="hidden" onChange={onFileInput} />
                    <div
                      onDragOver={(event) => {
                        event.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={onDrop}
                      className={`rounded-xl border border-dashed p-8 text-center transition ${
                        dragging ? "border-electric bg-electric/10" : "border-[var(--line)] bg-white/5"
                      }`}
                    >
                      <FileAudio className="mx-auto h-10 w-10 text-electric" />
                      <h3 className="mt-4 text-lg font-semibold text-[var(--text)]">Drag and drop your audio</h3>
                      <p className="mt-2 text-sm text-[var(--muted)]">Supported: {supportedAudio.join(", ")}. Max size: 10 MB.</p>
                      <Button type="button" variant="secondary" className="mt-5" onClick={() => inputRef.current?.click()}>
                        Browse file
                      </Button>
                    </div>
                  </div>
                )}

                {audioSource === "record" && (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--line)] bg-white/5 p-8 text-center">
                    {recordingStatus === "idle" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-electric/10 text-electric mb-4">
                          <Mic className="h-8 w-8" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--text)]">Record your voice</h3>
                        <p className="mt-2 text-sm text-[var(--muted)] mb-5">Click below to start recording. Max 25 seconds.</p>
                        <Button type="button" onClick={startRecording}>
                          <Mic className="h-4 w-4 mr-2" />
                          Start Recording
                        </Button>
                      </motion.div>
                    )}

                    {recordingStatus === "recording" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center w-full">
                        <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-rose-500/20 text-rose-500 mb-4 shadow-[0_0_20px_rgba(244,63,94,0.4)]">
                          <motion.div
                            animate={{ scale: [1, 1.2, 1] }}
                            transition={{ repeat: Infinity, duration: 1.5 }}
                            className="absolute inset-0 rounded-full bg-rose-500/20"
                          />
                          <Mic className="h-10 w-10 relative z-10" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--text)] text-rose-400">Recording...</h3>
                        <div className="mt-2 font-mono text-2xl font-bold tracking-wider text-white">
                          {formatTime(recordingTime)} / 00:25
                        </div>
                        <div className="w-full max-w-xs mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                          <motion.div 
                            className="h-full bg-rose-500" 
                            initial={{ width: 0 }} 
                            animate={{ width: `${(recordingTime / 25) * 100}%` }}
                          />
                        </div>
                        <Button type="button" variant="danger" className="mt-6" onClick={stopRecording}>
                          <Square className="h-4 w-4 mr-2 fill-current" />
                          Stop Recording
                        </Button>
                      </motion.div>
                    )}

                    {recordingStatus === "ready" && file && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center w-full">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 mb-4">
                          <Mic className="h-8 w-8" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--text)]">Recording Ready</h3>
                        
                        <div className="mt-4 flex gap-4 text-xs text-[var(--muted)]">
                          <span className="bg-white/5 px-2 py-1 rounded">Format: WEBM</span>
                          <span className="bg-white/5 px-2 py-1 rounded">Size: {formatBytes(file.size)}</span>
                        </div>
                        
                        <div className="w-full mt-6 bg-black/40 p-4 rounded-xl border border-white/5">
                          <audio src={previewUrl} controls className="w-full" />
                        </div>

                        <div className="flex gap-3 mt-6">
                          <Button type="button" variant="secondary" onClick={discardRecording}>
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete & Record Again
                          </Button>
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}

                {/* Common File Card for Both Audio Sources */}
                {file && (
                  <div className="rounded-xl border border-[var(--line)] bg-white/5 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[var(--text)]">{file.name}</p>
                        <p className="mt-1 text-xs text-[var(--muted)]">{formatBytes(file.size)}</p>
                      </div>
                      <Button type="button" variant="ghost" className="h-9 w-9 px-0" onClick={() => discardRecording()} aria-label="Remove file">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    {(fileError || extensionError) && <p className="mt-3 text-sm text-rose-300">{fileError || extensionError}</p>}
                    {busy && (
                      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                        <div className="h-full rounded-full bg-electric transition-all" style={{ width: `${uploadProgress}%` }} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {tab === "url" && (
              <div className="mt-5 space-y-5">
                <Input label="Video URL" placeholder="https://example.com/video.mp4" value={videoUrl} onChange={(event) => setVideoUrl(event.target.value)} error={!urlIsValid ? "Enter a valid http or https URL." : undefined} />
                <div className="rounded-xl border border-[var(--line)] bg-white/5 p-4">
                  <p className="text-sm font-semibold text-[var(--text)]">URL Preview</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                    Direct video links and supported video platforms preview here when the provider allows embedding.
                  </p>
                </div>
              </div>
            )}

            <Button className="mt-6 w-full" loading={busy} disabled={
              (tab === "upload_video" && (!file || Boolean(fileError || extensionError))) ||
              (tab === "audio" && audioSource === "record" && recordingStatus !== "ready") ||
              (tab === "audio" && audioSource === "upload" && (!file || Boolean(fileError || extensionError))) ||
              (tab === "url" && (!videoUrl || !urlIsValid))
            }>
              {busy ? "Preparing AI Job..." : tab === "audio" ? "Dub Audio" : "Dub Video"}
            </Button>
          </section>

          {/* ── Voice Settings Card ── */}
          <section className="glass rounded-xl p-5">
            <h2 className="text-lg font-semibold text-[var(--text)]">Voice Settings</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Configure voice generation and subtitle options.</p>

            <div className="mt-5 space-y-4">
              {/* Voice Cloning Toggle */}
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
              {tab !== "audio" && (
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

              {/* Enable Lip Sync Toggle */}
              {tab !== "audio" && (
                <label className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--line)] bg-white/5 px-4 py-3 transition hover:bg-white/[0.08]">
                  <div>
                    <p className="text-sm font-semibold text-[var(--text)]">Enable Lip Sync</p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">Synchronize the translated voice with the speaker's lip movements (Wav2Lip)</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={enableLipsync}
                    onClick={() => setEnableLipsync(!enableLipsync)}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                      enableLipsync ? "bg-electric" : "bg-zinc-600"
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${enableLipsync ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </label>
              )}
            </div>

            {/* Manual Voice Controls — visible only when Voice Cloning is OFF */}
            <AnimatePresence>
              {!voiceCloning && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: "easeInOut" }}
                  className="overflow-hidden"
                >
                  <div className="mt-5 space-y-4 border-t border-[var(--line)] pt-5">
                    <p className="text-sm font-semibold text-[var(--muted)]">Manual Voice Configuration</p>

                    <div className="grid gap-4 sm:grid-cols-2">
                      {/* Gender */}
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

                      {/* Age */}
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

                      {/* Pitch */}
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

                      {/* Style */}
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
          </section>
        </div>

        <section className="glass rounded-xl p-5">
          <div className="mb-4 flex items-center gap-3">
            {tab === "audio" ? <Mic className="h-5 w-5 text-electric" /> : <Video className="h-5 w-5 text-electric" />}
            <h2 className="text-lg font-semibold text-[var(--text)]">{tab === "audio" ? "Audio Preview" : "Video Preview"}</h2>
          </div>
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-xl border border-[var(--line)] bg-black/60">
            {tab === "upload_video" && previewUrl ? (
              <video src={previewUrl} controls className="h-full w-full object-contain" />
            ) : tab === "audio" && previewUrl ? (
              <div className="flex h-full w-full items-center justify-center bg-zinc-900/50 p-4">
                <audio src={previewUrl} controls className="w-full" />
              </div>
            ) : tab === "url" && urlIsValid && videoUrl ? (
              <MediaPreview url={videoUrl} title="External video preview" className="h-full" />
            ) : (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center">
                <PlayCircle className="mx-auto h-14 w-14 text-white/45" />
                <p className="mt-3 text-sm text-white/55">Preview appears here when possible.</p>
              </motion.div>
            )}
          </div>
          {tab === "url" && videoUrl && urlIsValid && (
            <div className="mt-4 flex justify-end">
              <Button type="button" variant="secondary" onClick={downloadOriginalFromUrl}>
                <Download className="h-4 w-4" />
                Download original
              </Button>
            </div>
          )}
          <div className="mt-5 rounded-xl border border-[var(--line)] bg-white/5 p-4">
            <p className="text-sm font-semibold text-[var(--text)]">UX status</p>
            <p className="mt-2 text-sm text-[var(--muted)]">{busy ? "Uploading... Preparing AI Job..." : tab === "audio" ? "Waiting for your audio source." : "Waiting for your video source."}</p>
          </div>
        </section>
      </form>
    </AppShell>
  );
}
