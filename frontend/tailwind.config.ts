import type { Config } from "tailwindcss";

// Tailwind configuration: scans the app, components and lib folders for classes.
// The typography plugin is loaded via require() because it ships without TS types,
// which keeps `next build` type-checking clean.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette aligned with the project design system.
        brand: {
          navy: "#1F3864",
          azure: "#2E75B6",
          light: "#D6E4F0",
        },
      },
    },
  },
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  plugins: [require("@tailwindcss/typography")],
};

export default config;
