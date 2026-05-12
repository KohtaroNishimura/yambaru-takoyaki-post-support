import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#ec6d3b",
        ocean: "#0f6674",
        leaf: "#5b8a32",
      },
    },
  },
  plugins: [],
};

export default config;
