/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./frontend/**/*.html",
    "./frontend/**/*.js"
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "secondary-fixed": "#6bfe9c",
        "surface-container-lowest": "rgba(13, 20, 36, 0.45)",
        "inverse-surface": "#f8f9fa",
        "on-error-container": "#93000a",
        "outline-variant": "rgba(255, 255, 255, 0.08)",
        "inverse-primary": "#bac3ff",
        "surface-container": "rgba(255, 255, 255, 0.06)",
        "on-primary-fixed": "#00105c",
        "tertiary": "#6c3400",
        "surface": "#0d1424",
        "on-error": "#ffffff",
        "on-background": "#f0f4ff",
        "on-surface-variant": "#8892a4",
        "tertiary-fixed": "#ffdcc6",
        "on-primary-fixed-variant": "#293ca0",
        "surface-bright": "#121b30",
        "on-secondary-container": "#00743a",
        "surface-dim": "#080b14",
        "on-surface": "#f0f4ff",
        "on-tertiary": "#ffffff",
        "surface-tint": "#4f46e5",
        "secondary": "#00bfa5",
        "secondary-fixed-dim": "#4ae183",
        "on-secondary": "#ffffff",
        "on-primary": "#ffffff",
        "primary": "#4f46e5",
        "error-container": "#ffdad6",
        "on-tertiary-container": "#ffc7a2",
        "on-tertiary-fixed": "#301400",
        "primary-fixed": "#dee0ff",
        "on-secondary-fixed-variant": "#005228",
        "surface-container-highest": "rgba(255, 255, 255, 0.12)",
        "surface-container-low": "rgba(255, 255, 255, 0.02)",
        "error": "#ef4444",
        "inverse-on-surface": "#191c1d",
        "surface-variant": "rgba(255, 255, 255, 0.08)",
        "tertiary-container": "#8f4700",
        "on-primary-container": "#cacfff",
        "outline": "rgba(255, 255, 255, 0.16)",
        "surface-container-high": "rgba(255, 255, 255, 0.08)",
        "primary-container": "rgba(79, 70, 229, 0.2)",
        "secondary-container": "#6bfe9c",
        "on-tertiary-fixed-variant": "#713700",
        "primary-fixed-dim": "#bac3ff",
        "background": "#080b14",
        "on-secondary-fixed": "#00210c",
        "tertiary-fixed-dim": "#ffb784"
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      spacing: {
        "sm": "12px",
        "gutter": "24px",
        "xl": "64px",
        "md": "24px",
        "lg": "40px",
        "xs": "4px",
        "container-max": "1200px",
        "base": "8px"
      },
      fontFamily: {
        "title-md": ["Manrope"],
        "body-md": ["Work Sans"],
        "label-md": ["Manrope"],
        "body-sm": ["Work Sans"],
        "body-lg": ["Work Sans"],
        "headline-lg-mobile": ["Manrope"],
        "display-lg": ["Manrope"],
        "headline-lg": ["Manrope"]
      },
      fontSize: {
        "title-md": ["20px", { "lineHeight": "28px", "fontWeight": "600" }],
        "body-md": ["16px", { "lineHeight": "24px", "fontWeight": "400" }],
        "label-md": ["12px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "600" }],
        "body-sm": ["14px", { "lineHeight": "20px", "fontWeight": "400" }],
        "body-lg": ["18px", { "lineHeight": "28px", "fontWeight": "400" }],
        "headline-lg-mobile": ["24px", { "lineHeight": "32px", "fontWeight": "600" }],
        "display-lg": ["48px", { "lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700" }],
        "headline-lg": ["32px", { "lineHeight": "40px", "fontWeight": "600" }]
      }
    }
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/container-queries")
  ]
}
