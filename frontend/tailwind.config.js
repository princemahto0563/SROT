/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:          "rgb(var(--color-bg) / <alpha-value>)",
        surface:     "rgb(var(--color-surface) / <alpha-value>)",
        s2:          "rgb(var(--color-s2) / <alpha-value>)",
        s3:          "rgb(var(--color-s3) / <alpha-value>)",
        line:        "rgb(var(--color-line) / <alpha-value>)",
        lineSoft:    "rgb(var(--color-line-soft) / <alpha-value>)",
        ink:         "rgb(var(--color-ink) / <alpha-value>)",
        ink2:        "rgb(var(--color-ink2) / <alpha-value>)",
        muted:       "rgb(var(--color-muted) / <alpha-value>)",
        accent:      "rgb(var(--color-accent) / <alpha-value>)",
        accentBright:"rgb(var(--color-accent-bright) / <alpha-value>)",
        "accent-ink":"rgb(var(--color-accent-ink) / <alpha-value>)",
        amber:       "rgb(var(--color-amber) / <alpha-value>)",
        danger:      "rgb(var(--color-danger) / <alpha-value>)",
        ok:          "rgb(var(--color-ok) / <alpha-value>)",
        violet:      "rgb(var(--color-violet) / <alpha-value>)",
      },
      fontFamily: {
        sans: ['"Inter"','system-ui','-apple-system','"Segoe UI"','Roboto','sans-serif'],
        mono: ['"JetBrains Mono"','ui-monospace','"SF Mono"','Menlo','Consolas','monospace'],
      },
      boxShadow: { 
        panel: "var(--panel-shadow)",
      },
    },
  },
  plugins: [],
}
