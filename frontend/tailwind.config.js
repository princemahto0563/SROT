/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0B1017",
        surface: "#121A24",
        s2:      "#17222F",
        s3:      "#1E2B3A",
        line:    "#223141",
        lineSoft:"#1A2634",
        ink:     "#E9EFF5",
        ink2:    "#97A9BC",
        muted:   "#6C7F94",
        accent:  "#4CA6E8",
        amber:   "#E9A33A",
        danger:  "#E5605C",
        ok:      "#3FB98A",
        violet:  "#9B96E8",
      },
      fontFamily: {
        sans: ['"Inter"','system-ui','-apple-system','"Segoe UI"','Roboto','sans-serif'],
        mono: ['"JetBrains Mono"','ui-monospace','"SF Mono"','Menlo','Consolas','monospace'],
      },
      boxShadow: { panel: "0 1px 0 rgba(255,255,255,.03) inset, 0 8px 28px rgba(0,0,0,.34)" },
    },
  },
  plugins: [],
}
