/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./charts/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: "#0b0e14",
          800: "#121721",
          700: "#1a2233",
          600: "#242f45",
        },
        trade: {
          green: "#0ecb81",
          red: "#f6465d",
          cyan: "#00f0ff",
        },
      },
    },
  },
  plugins: [],
};
