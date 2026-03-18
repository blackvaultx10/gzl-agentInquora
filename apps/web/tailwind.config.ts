import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 品牌主色
        primary: {
          DEFAULT: "#e4572e",
          light: "rgba(228, 87, 46, 0.18)",
          dark: "rgba(228, 87, 46, 0.24)",
        },
        // 背景色
        page: {
          DEFAULT: "#f6efe3",
          ink: "#f6efe3",
        },
        paper: {
          DEFAULT: "rgba(255, 250, 244, 0.86)",
          strong: "rgba(255, 252, 247, 0.96)",
        },
        // 文字色
        ink: {
          DEFAULT: "#211f1a",
          light: "rgba(33, 31, 26, 0.72)",
          muted: "rgba(89, 76, 60, 0.72)",
        },
        // 边框/线条
        line: {
          DEFAULT: "rgba(68, 57, 43, 0.12)",
          strong: "rgba(68, 57, 43, 0.18)",
        },
        // 辅助色
        accent: {
          blue: "rgba(28, 76, 112, 0.12)",
          orange: "rgba(228, 87, 46, 0.05)",
          warm: "rgba(255, 245, 234, 0.74)",
        },
        // 状态色
        status: {
          flagged: "rgba(255, 245, 234, 0.74)",
          clean: "rgba(255, 255, 255, 0.68)",
        },
      },
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        panel: "34px",
        card: "30px",
        metric: "28px",
        upload: "26px",
        pill: "999px",
      },
      boxShadow: {
        panel: "0 24px 70px rgba(48, 37, 24, 0.14)",
        button: "0 12px 28px rgba(228, 87, 46, 0.24)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "hero-gradient":
          "linear-gradient(120deg, rgba(255, 250, 244, 0.96), rgba(246, 239, 227, 0.9))",
        "metric-gradient":
          "linear-gradient(180deg, rgba(255, 255, 255, 0.8), rgba(255, 244, 239, 0.85))",
        "uploader-gradient":
          "linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(244, 236, 224, 0.7))",
      },
      backdropBlur: {
        card: "12px",
      },
      transitionProperty: {
        sidebar: "width, transform, opacity",
      },
      width: {
        sidebar: "240px",
        "sidebar-collapsed": "64px",
      },
    },
  },
  plugins: [],
};

export default config;
