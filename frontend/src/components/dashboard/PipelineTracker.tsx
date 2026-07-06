import { CheckCircle2, CircleDotDashed, FileVideo, RadioTower, WandSparkles } from "lucide-react";
import { motion } from "framer-motion";
import type { TranslationDto } from "../../types/api";
import { Badge } from "../ui/Badge";
import { normalizeStatus } from "../../lib/status";

const steps = [
  { label: "Uploading to Storage", icon: FileVideo, threshold: 5 },
  { label: "Queueing", icon: CircleDotDashed, threshold: 20 },
  { label: "AI Processing", icon: WandSparkles, threshold: 95 },
  { label: "Finalizing & Ready", icon: CheckCircle2, threshold: 100 }
];

interface PipelineTrackerProps {
  translation?: TranslationDto | null;
  uploadProgress: number;
  isUploading: boolean;
}

export function PipelineTracker({ translation, uploadProgress, isUploading }: PipelineTrackerProps) {
  const progress = isUploading ? uploadProgress : translation?.progress ?? 0;
  const status = isUploading ? "Uploading" : translation ? normalizeStatus(translation.status) : "Idle";
  const isTerminal = ["Completed", "Failed", "Cancelled"].includes(status);

  return (
    <section className="glass rounded-lg p-5">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-electric">Live Pipeline</p>
          <h2 className="mt-2 text-xl font-bold text-white">Real-time process tracker</h2>
        </div>
        <Badge>{status}</Badge>
      </div>

      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between text-sm text-slate-300">
          <span>{translation?.video?.fileName || translation?.audio?.fileName || "Waiting for job"}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-white/10">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-electric to-violet"
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(progress, 100)}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {steps.map((step) => {
          const active = progress >= step.threshold || (step.threshold === 5 && progress > 0);
          return (
            <motion.div
              key={step.label}
              className={`rounded-lg border p-4 transition ${
                active ? "border-electric/40 bg-electric/10" : "border-line bg-white/5"
              }`}
              animate={{ scale: active && !isTerminal ? [1, 1.02, 1] : 1 }}
              transition={{ repeat: active && !isTerminal ? Infinity : 0, duration: 1.8 }}
            >
              <step.icon className={active ? "h-6 w-6 text-electric" : "h-6 w-6 text-slate-500"} />
              <p className="mt-4 text-sm font-semibold text-white">{step.label}</p>
            </motion.div>
          );
        })}
      </div>

      {translation?.errorMessage && <p className="mt-4 rounded-md bg-rose-500/10 p-3 text-sm text-rose-100">{translation.errorMessage}</p>}
      {!translation && !isUploading && (
        <div className="mt-5 flex items-center gap-3 rounded-lg border border-line bg-white/5 p-4 text-sm text-slate-400">
          <RadioTower className="h-5 w-5 text-electric" />
          Submit media to activate polling and animated state transitions.
        </div>
      )}
    </section>
  );
}
