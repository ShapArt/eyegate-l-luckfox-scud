import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Sora'", "'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "SFMono-Regular", "ui-monospace", "monospace"],
      },
      colors: {
        base: "#0b1118",
        surface: "#0f1724",
        surfaceAlt: "#0c1422",
        border: "#1d2736",
        accent: "#5cd4ff",
        accent2: "#4cc38a",
        success: "#4cc38a",
        warning: "#f4b63f",
        danger: "#ff6b6b",
        muted: "#90a3bc",
      },
      boxShadow: {
        card: "0 14px 40px rgba(0,0,0,0.35)",
        soft: "0 6px 18px rgba(0,0,0,0.22)",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "fade-in": "fadeIn 400ms ease forwards",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
