import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070911",
        panel: "#0d111c",
        line: "rgba(148, 163, 184, 0.18)",
        electric: "#2dd4ff",
        violet: "#8b5cf6"
      },
      boxShadow: {
        glow: "0 0 32px rgba(45, 212, 255, 0.22)",
        violet: "0 0 36px rgba(139, 92, 246, 0.25)"
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)"
      }
    }
  },
  plugins: []
} satisfies Config;
