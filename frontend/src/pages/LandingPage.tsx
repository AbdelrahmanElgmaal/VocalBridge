import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Languages, Mic2, PlayCircle, ShieldCheck, Sparkles, WandSparkles } from "lucide-react";
import { Button } from "../components/ui/Button";
import { useLogout } from "../hooks/useAuth";
import { tokenStore } from "../lib/auth";

const features = [
  { icon: Languages, title: "English to Arabic dubbing", description: "A focused workflow for high-quality Arabic video localization." },
  { icon: Mic2, title: "AI voice generation", description: "Generate natural Arabic speech from translated transcripts." },
  { icon: ShieldCheck, title: "Secure media workflow", description: "Authenticated uploads, signed URLs, and private job history." }
];

const steps = [
  {
    title: "Upload or Paste URL",
    description: "Upload your video file or paste an external video link to get started."
  },
  {
    title: "Extract Audio",
    description: "Separate the audio track from the uploaded video."
  },
  {
    title: "Speech Recognition",
    description: "Convert English speech into text using Whisper AI."
  },
  {
    title: "Translate",
    description: "Translate the English transcript into Arabic."
  },
  {
    title: "Voice Generation",
    description: "Generate Arabic speech using AI voice synthesis."
  },
  {
    title: "Download or Watch Result",
    description: "Merge everything back into the video and download your final dubbed masterpiece."
  }
];

export function LandingPage() {
  const logout = useLogout();
  const isAuthenticated = tokenStore.isAuthenticated();

  return (
    <main className="min-h-screen overflow-hidden">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-electric/15 text-electric shadow-glow">
            <Sparkles className="h-6 w-6" />
          </span>
          <span className="text-lg font-bold text-[var(--text)]">Vocal Bridge</span>
        </Link>
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <button
              type="button"
              onClick={logout}
              className="text-sm font-semibold text-[var(--muted)] transition hover:text-[var(--text)]"
            >
              Sign Out
            </button>
          ) : (
            <Link to="/login" className="text-sm font-semibold text-[var(--muted)] transition hover:text-[var(--text)]">
              Login
            </Link>
          )}
          <Link to="/translate">
            <Button>
              Start dubbing
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </nav>

      <section className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-7xl items-center gap-12 px-4 py-10 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8">
        <motion.div initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.55 }}>
          <p className="mb-5 inline-flex rounded-full border border-electric/25 bg-electric/10 px-3 py-1 text-sm font-semibold text-electric">
            AI video dubbing for production teams
          </p>
          <h1 className="max-w-4xl text-5xl font-bold tracking-tight text-[var(--text)] sm:text-6xl lg:text-7xl">
            Translate video into Arabic with a cinematic AI pipeline.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)]">
            Vocal Bridge turns uploaded videos or direct links into dubbed Arabic video assets with real-time progress, secure media handling, and a clean SaaS workflow.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/translate">
              <Button className="h-12 px-6">
                Create dubbing
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button variant="secondary" className="h-12 px-6">
                View dashboard
              </Button>
            </Link>
          </div>
        </motion.div>

        <motion.div
          className="glass relative rounded-2xl p-4 shadow-violet"
          initial={{ y: 24, opacity: 0, scale: 0.98 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          transition={{ delay: 0.12, duration: 0.55 }}
        >
          <div className="rounded-xl border border-[var(--line)] bg-black/40 p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-[var(--text)]">Dubbing pipeline</p>
                <p className="text-xs text-[var(--muted)]">Processing lecture_demo.mp4</p>
              </div>
              <span className="rounded-full bg-emerald-400/12 px-3 py-1 text-xs font-semibold text-emerald-200">78%</span>
            </div>
            <div className="aspect-video rounded-xl bg-gradient-to-br from-electric/20 via-violet/20 to-black p-5">
              <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-black/30">
                <PlayCircle className="h-16 w-16 text-white/80" />
              </div>
            </div>
            <div className="mt-5 space-y-3">
              {["Speech Recognition", "Translate", "Voice Generation", "Merge Audio & Video"].map((item, index) => (
                <div key={item} className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3">
                  {index < 2 ? <CheckCircle2 className="h-5 w-5 text-emerald-300" /> : <WandSparkles className="h-5 w-5 text-electric" />}
                  <span className="text-sm font-medium text-white">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="grid gap-4 md:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title} className="glass rounded-xl p-6">
              <feature.icon className="h-7 w-7 text-electric" />
              <h3 className="mt-5 text-lg font-semibold text-[var(--text)]">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <div className="glass rounded-2xl p-8">
          <h2 className="text-3xl font-bold text-[var(--text)]">How it works</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {steps.map((step, index) => (
              <div key={step.title} className="rounded-xl border border-[var(--line)] bg-white/5 p-6 transition hover:border-electric/35 hover:bg-white/[0.07]">
                <span className="text-sm font-bold tracking-[0.2em] text-electric">0{index + 1}</span>
                <h3 className="mt-5 text-lg font-semibold text-[var(--text)]">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{step.description}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--line)] pt-6">
            <p className="text-sm text-[var(--muted)]">Ready to localize your first video?</p>
            <Link to="/translate">
              <Button>Create dubbing</Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-[var(--line)] px-4 py-8 text-center text-sm text-[var(--muted)]">
        Vocal Bridge. AI-powered Arabic dubbing for modern teams.
      </footer>
    </main>
  );
}
