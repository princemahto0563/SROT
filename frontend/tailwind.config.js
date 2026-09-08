/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:          "#08090D",
        surface:     "#10121A",
        s2:          "#171A24",
        s3:          "#1D202B",
        line:        "#292D3A",
        lineSoft:    "#202330",
        ink:         "#F1F2F6",
        ink2:        "#9297A6",
        muted:       "#686E7D",
        accent:      "#9B7BFF",
        accentBright:"#B9A3FF",
        "accent-ink":"#08090D",
        amber:       "#E5B85C",
        danger:      "#E05D6F",
        ok:          "#55C98A",
        violet:      "#B9A3FF",
      },
      fontFamily: {
        sans: ['"Inter"','system-ui','-apple-system','"Segoe UI"','Roboto','sans-serif'],
        mono: ['"JetBrains Mono"','ui-monospace','"SF Mono"','Menlo','Consolas','monospace'],
      },
      boxShadow: { panel: "0 1px 0 rgba(255,255,255,.03) inset, 0 8px 28px rgba(0,0,0,.45)" },
    },
  },
  plugins: [],
}
