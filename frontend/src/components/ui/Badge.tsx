import { ReactNode } from "react";
import { cn } from "../../lib/utils";

const toneMap: Record<string, string> = {
  queued: "border-sky-400/30 bg-sky-400/12 text-sky-200",
  processing: "border-violet-400/30 bg-violet-400/12 text-violet-100",
  completed: "border-emerald-400/30 bg-emerald-400/12 text-emerald-100",
  failed: "border-rose-400/30 bg-rose-400/12 text-rose-100",
  cancelled: "border-amber-400/30 bg-amber-400/12 text-amber-100"
};

export function Badge({ children, className, toneKey }: { children: ReactNode; className?: string; toneKey?: string }) {
  const key = toneKey ?? (typeof children === "string" ? children : "");
  const tone = toneMap[key.toLowerCase()] ?? "border-slate-400/30 bg-slate-400/12 text-slate-100";
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold", tone, className)}>
      {children}
    </span>
  );
}
