/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{html,jsx,tsx,vue,js,ts}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bp: {
          bg: "#060810",
          surface: "#0a0f1a",
          card: "rgba(255,255,255,0.03)",
          border: "rgba(255,255,255,0.06)",
          "border-hover": "rgba(255,255,255,0.12)",
          green: "#22c55e",
          cyan: "#06b6d4",
          red: "#ef4444",
          amber: "#f59e0b",
          purple: "#a855f7",
          text: "rgba(255,255,255,0.9)",
          muted: "rgba(255,255,255,0.5)",
          dim: "rgba(255,255,255,0.3)",
        },
      },
      fontFamily: {
        sans: ["DM Sans", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        shimmer: "shimmer 2s linear infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "fade-up": "fade-up 0.5s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        "gradient-shift": "gradient-shift 3s ease infinite",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          "0%": { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
    },
  },
  plugins: [],
};
