import { cn } from "../../lib/utils";

interface ChartItem {
  label: string;
  value: number;
}

interface DashboardChartProps {
  title: string;
  items: ChartItem[];
  emptyText: string;
}

export function DashboardChart({ title, items, emptyText }: DashboardChartProps) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const visibleItems = items.filter((item) => item.value > 0);

  return (
    <section className="glass rounded-xl p-5">
      <h2 className="text-lg font-semibold text-[var(--text)]">{title}</h2>
      {total === 0 ? (
        <p className="mt-4 rounded-lg border border-[var(--line)] bg-white/5 p-4 text-sm text-[var(--muted)]">{emptyText}</p>
      ) : (
        <div className="mt-5 space-y-4">
          {visibleItems.map((item, index) => {
            const percentage = Math.round((item.value / total) * 100);
            return (
              <div key={item.label}>
                <div className="mb-2 flex items-center justify-between gap-4 text-sm">
                  <span className="font-medium text-zinc-200">{item.label}</span>
                  <span className="text-zinc-400">{item.value} / {percentage}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      index % 3 === 0 ? "bg-electric" : index % 3 === 1 ? "bg-violet" : "bg-emerald-300"
                    )}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
