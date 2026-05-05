import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#070810",
          panel: "#0e1018",
          elev: "#161927",
          deep: "#04050a",
          border: "#1c2030",
          edge: "#262a3d",
        },
        accent: {
          green: "#22c55e",
          red: "#ef4444",
          blue: "#3b82f6",
          amber: "#f59e0b",
          violet: "#8b5cf6",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      keyframes: {
        flashGreen: {
          "0%, 100%": { backgroundColor: "transparent" },
          "30%": { backgroundColor: "rgba(34,197,94,0.18)" },
        },
        flashRed: {
          "0%, 100%": { backgroundColor: "transparent" },
          "30%": { backgroundColor: "rgba(239,68,68,0.18)" },
        },
      },
      animation: {
        flashGreen: "flashGreen 700ms ease-out",
        flashRed: "flashRed 700ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
