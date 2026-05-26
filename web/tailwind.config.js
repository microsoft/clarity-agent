/** @type {import('tailwindcss').Config} */

// The package is ``"type": "module"`` so this file is ESM — use
// ``import`` for plugins instead of CommonJS ``require()``.
import typography from "@tailwindcss/typography";

/* Helper: reference a CSS custom property with Tailwind alpha support */
const themeColor = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        sidebar: "var(--font-sidebar)",
        mono: "var(--font-mono)",
      },
      colors: {
        sidebar: {
          DEFAULT: themeColor("sidebar"),
          active: themeColor("sidebar-active"),
          line: themeColor("sidebar-line"),
          text: themeColor("sidebar-text"),
          "text-secondary": themeColor("sidebar-text-secondary"),
          "text-muted": themeColor("sidebar-text-muted"),
          "text-faint": themeColor("sidebar-text-faint"),
        },
        surface: {
          DEFAULT: themeColor("surface"),
          ground: themeColor("surface-ground"),
          dim: themeColor("surface-dim"),
          muted: themeColor("surface-muted"),
        },
        body: {
          DEFAULT: themeColor("text"),
          heading: themeColor("text-heading"),
          label: themeColor("text-label"),
          muted: themeColor("text-muted"),
          faint: themeColor("text-faint"),
        },
        border: {
          DEFAULT: themeColor("border"),
          strong: themeColor("border-strong"),
          dim: themeColor("border-dim"),
        },
        accent: {
          DEFAULT: themeColor("accent"),
          hover: themeColor("accent-hover"),
          focus: themeColor("accent-focus"),
          surface: themeColor("accent-surface"),
          "surface-border": themeColor("accent-surface-border"),
          "surface-text": themeColor("accent-surface-text"),
          "surface-body": themeColor("accent-surface-body"),
          "surface-muted": themeColor("accent-surface-muted"),
          "surface-faint": themeColor("accent-surface-faint"),
        },
        status: {
          ok: themeColor("status-ok"),
          "ok-bg": themeColor("status-ok-bg"),
          "ok-text": themeColor("status-ok-text"),
          warn: themeColor("status-warn"),
          "warn-bg": themeColor("status-warn-bg"),
          "warn-text": themeColor("status-warn-text"),
          error: themeColor("status-error"),
          "error-bg": themeColor("status-error-bg"),
          "error-text": themeColor("status-error-text"),
          info: themeColor("status-info"),
          "info-bg": themeColor("status-info-bg"),
          "info-text": themeColor("status-info-text"),
        },
        "shadow-accent": themeColor("shadow-accent"),
        disabled: {
          DEFAULT: themeColor("disabled"),
          surface: themeColor("disabled-surface"),
          text: themeColor("disabled-text"),
        },
        code: {
          bg: themeColor("code-bg"),
          text: themeColor("code-text"),
        },
      },
      typography: {
        DEFAULT: {
          css: {
            "--tw-prose-body": "rgb(var(--text))",
            "--tw-prose-headings": "rgb(var(--text-heading))",
            "--tw-prose-bold": "rgb(var(--text))",
            "--tw-prose-links": "rgb(var(--accent))",
            "--tw-prose-counters": "rgb(var(--text-muted))",
            "--tw-prose-bullets": "rgb(var(--text-muted))",
            "--tw-prose-hr": "rgb(var(--border))",
            "--tw-prose-quotes": "rgb(var(--text-label))",
            "--tw-prose-quote-borders": "rgb(var(--border))",
            "--tw-prose-captions": "rgb(var(--text-muted))",
            "--tw-prose-th-borders": "rgb(var(--border-strong))",
            "--tw-prose-td-borders": "rgb(var(--border))",
          },
        },
      },
    },
  },
  plugins: [typography],
};
