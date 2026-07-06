import { ReactNode, useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { BarChart3, ChevronLeft, History, LogOut, Menu, PlusCircle, Sparkles, Video } from "lucide-react";
import { motion } from "framer-motion";
import { useLogout } from "../../hooks/useAuth";
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/translate", label: "Create", icon: PlusCircle },
  { to: "/history", label: "History", icon: History }
];

const SIDEBAR_COLLAPSED_KEY = "vocalBridge.sidebarCollapsed";

export function AppShell({ children }: { children: ReactNode }) {
  const logout = useLogout();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true");

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  return (
    <div className="min-h-screen bg-[#09090b] bg-grid bg-[length:34px_34px] text-zinc-100">
      <aside
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 border-t border-zinc-800/80 bg-[#0d0d12]/95 backdrop-blur-xl transition-all duration-300 md:inset-y-0 md:left-0 md:right-auto md:border-r md:border-t-0",
          collapsed ? "md:w-20" : "md:w-72"
        )}
      >
        <div className="hidden h-24 items-center justify-between gap-3 px-4 md:flex">
          <Link to="/" className={cn("flex min-w-0 items-center gap-3", collapsed && "justify-center")}>
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-electric/15 text-electric shadow-glow">
            <Sparkles className="h-6 w-6" />
          </div>
          <div className={cn("min-w-0 transition-opacity", collapsed && "hidden")}>
            <p className="text-lg font-bold text-[var(--text)]">Vocal Bridge</p>
            <p className="text-xs text-[var(--muted)]">AI Dubbing Platform</p>
          </div>
          </Link>
          <Button
            variant="ghost"
            className="h-9 w-9 shrink-0 px-0"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "Open sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <Menu className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          </Button>
        </div>

        <nav className={cn("flex items-center justify-around p-2 md:block md:space-y-2", collapsed ? "md:px-3" : "md:px-4")}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 rounded-md px-4 py-3 text-sm font-semibold text-slate-400 transition hover:bg-white/10 hover:text-white",
                  collapsed && "md:justify-center md:px-0",
                  isActive && "bg-white/10 text-[var(--text)]"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span layoutId="nav-active" className="absolute inset-y-2 left-0 w-1 rounded-full bg-electric" />
                  )}
                  <item.icon className="h-5 w-5" />
                  <span className={cn("hidden md:inline", collapsed && "md:hidden")}>{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={cn("hidden px-4 md:absolute md:bottom-6 md:block md:w-full", collapsed && "md:px-3")}>
          <div className={cn("glass mb-4 rounded-lg p-4", collapsed && "hidden")}>
            <Video className="mb-3 h-5 w-5 text-electric" />
            <p className="text-sm font-semibold text-[var(--text)]">Production Studio</p>
            <p className="mt-1 text-xs leading-5 text-[var(--muted)]">Create dubbing jobs, monitor progress, and manage media.</p>
          </div>
          <Button variant="ghost" className={cn("w-full justify-start", collapsed && "justify-center px-0")} onClick={logout}>
            <LogOut className="h-4 w-4" />
            <span className={cn(collapsed && "hidden")}>Sign out</span>
          </Button>
        </div>
      </aside>

      <main className={cn("pb-24 transition-all duration-300 md:pb-0", collapsed ? "md:ml-20" : "md:ml-72")}>
        <div className="mx-auto min-h-screen w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
