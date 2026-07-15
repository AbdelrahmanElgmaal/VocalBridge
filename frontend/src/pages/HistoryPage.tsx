import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { HistoryGrid } from "../components/history/HistoryGrid";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useTranslations } from "../hooks/useTranslations";
import { getApiError } from "../lib/api";
import { filterHistoryJobs, type HistoryFilter, type HistorySort } from "../lib/historyFilters";

const filters: { value: HistoryFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "videos", label: "Videos" },
  { value: "audio", label: "Audio" },
  { value: "recordedAudio", label: "Recorded Audio" },
  { value: "uploadedAudio", label: "Uploaded Audio" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" }
];

const sorts: { value: HistorySort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" }
];

export function HistoryPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const translations = useTranslations(true);

  const routeState = location.state as { filter?: HistoryFilter } | null;

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<HistoryFilter>(routeState?.filter ?? "all");
  const [sort, setSort] = useState<HistorySort>("newest");

  const jobs = translations.data ?? [];
  const filteredJobs = useMemo(
    () => filterHistoryJobs(jobs, { search, filter, sort }),
    [filter, jobs, search, sort]
  );

  return (
    <AppShell>
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-electric">History</p>
          <h1 className="mt-2 text-3xl font-bold text-white md:text-4xl">Dubbing History</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
            Search, preview, retry, and manage every video and audio translation job.
          </p>
        </div>
        <Button onClick={() => navigate("/translate")}>Create Dubbing</Button>
      </div>

      {translations.isError ? (
        <ErrorCard message={getApiError(translations.error)} onRetry={() => translations.refetch()} />
      ) : (
        <>
          <section className="glass mb-6 rounded-xl p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_180px_180px]">
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search file name or job ID"
                  className="h-11 w-full rounded-md border border-zinc-800 bg-white/[0.07] pl-9 pr-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                />
              </label>
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value as HistoryFilter)}
                className="h-11 rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                aria-label="Filter jobs"
              >
                {filters.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as HistorySort)}
                className="h-11 rounded-md border border-zinc-800 bg-[#111116] px-3 text-sm text-zinc-100 outline-none ring-electric/30 focus:ring-2"
                aria-label="Sort jobs"
              >
                {sorts.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
          </section>

          {translations.isLoading ? (
            <div className="grid gap-4 lg:grid-cols-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-72 w-full" />
              ))}
            </div>
          ) : filteredJobs.length ? (
            <HistoryGrid jobs={filteredJobs} />
          ) : (
            <EmptyState
              icon={<Search className="h-7 w-7" />}
              title={jobs.length ? "No matching jobs" : "No translation jobs yet"}
              description={jobs.length ? "Adjust search, filter, or sort to find jobs." : "Create a video or audio dub and it will appear in history."}
              actionLabel={jobs.length ? undefined : "Create Dubbing"}
              onAction={jobs.length ? undefined : () => navigate("/translate")}
            />
          )}
        </>
      )}
    </AppShell>
  );
}
