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
        "surface-container-lowest": "#ffffff",
        "inverse-surface": "#2e3132",
        "on-error-container": "#93000a",
        "outline-variant": "#c5c5d4",
        "inverse-primary": "#bac3ff",
        "surface-container": "#edeeef",
        "on-primary-fixed": "#00105c",
        "tertiary": "#6c3400",
        "surface": "#f8f9fa",
        "on-error": "#ffffff",
        "on-background": "#191c1d",
        "on-surface-variant": "#454652",
        "tertiary-fixed": "#ffdcc6",
        "on-primary-fixed-variant": "#293ca0",
        "surface-bright": "#f8f9fa",
        "on-secondary-container": "#00743a",
        "surface-dim": "#d9dadb",
        "on-surface": "#191c1d",
        "on-tertiary": "#ffffff",
        "surface-tint": "#4355b9",
        "secondary": "#006d37",
        "secondary-fixed-dim": "#4ae183",
        "on-secondary": "#ffffff",
        "on-primary": "#ffffff",
        "primary": "#24389c",
        "error-container": "#ffdad6",
        "on-tertiary-container": "#ffc7a2",
        "on-tertiary-fixed": "#301400",
        "primary-fixed": "#dee0ff",
        "on-secondary-fixed-variant": "#005228",
        "surface-container-highest": "#e1e3e4",
        "surface-container-low": "#f3f4f5",
        "error": "#ba1a1a",
        "inverse-on-surface": "#f0f1f2",
        "surface-variant": "#e1e3e4",
        "tertiary-container": "#8f4700",
        "on-primary-container": "#cacfff",
        "outline": "#757684",
        "surface-container-high": "#e7e8e9",
        "primary-container": "#3f51b5",
        "secondary-container": "#6bfe9c",
        "on-tertiary-fixed-variant": "#713700",
        "primary-fixed-dim": "#bac3ff",
        "background": "#f8f9fa",
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
