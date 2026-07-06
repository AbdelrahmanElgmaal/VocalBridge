import { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface QuickActionCardProps {
  title: string;
  description: string;
  icon: ReactNode;
  onClick: () => void;
  tone?: "default" | "danger";
}

export function QuickActionCard({ title, description, icon, onClick, tone = "default" }: QuickActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group rounded-lg border p-4 text-left transition focus:outline-none focus:ring-2 focus:ring-electric/40",
        tone === "danger"
          ? "border-rose-400/20 bg-rose-500/10 hover:border-rose-300/40"
          : "border-[var(--line)] bg-white/5 hover:border-electric/40 hover:bg-electric/10"
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-md transition",
          tone === "danger" ? "bg-rose-400/15 text-rose-200" : "bg-electric/12 text-electric group-hover:bg-electric/20"
        )}
      >
        {icon}
      </div>
      <p className="mt-4 text-sm font-semibold text-[var(--text)]">{title}</p>
      <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{description}</p>
    </button>
  );
}
