import { ReactNode } from "react";
import { motion } from "framer-motion";

interface MetricCardProps {
  label: string;
  value: number | string;
  icon: ReactNode;
  tone?: "cyan" | "violet" | "green" | "amber";
}

const tones = {
  cyan: "text-electric shadow-glow",
  violet: "text-violet shadow-violet",
  green: "text-emerald-300",
  amber: "text-amber-300"
};

export function MetricCard({ label, value, icon, tone = "cyan" }: MetricCardProps) {
  return (
    <motion.div
      className="glass rounded-lg p-5"
      initial={{ y: 12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      whileHover={{ y: -3 }}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">{label}</p>
        <div className={`flex h-10 w-10 items-center justify-center rounded-md bg-white/10 ${tones[tone]}`}>{icon}</div>
      </div>
      <p className="mt-4 text-3xl font-bold text-white">{value}</p>
    </motion.div>
  );
}
