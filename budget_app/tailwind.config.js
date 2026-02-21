/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        zen: {
          stone: {
            light: '#FEFEFE',
            DEFAULT: '#F5F5F0',
            dark: '#E8E8E3',
          },
          sage: {
            light: '#A8C5A5',
            DEFAULT: '#8BA888',
            dark: '#6B8E6B',
          },
          sand: {
            light: '#E5D9C8',
            DEFAULT: '#D4C5B0',
            dark: '#C4B29F',
          },
          charcoal: {
            light: '#5A5A5A',
            DEFAULT: '#3A3A3A',
            dark: '#2C2C2C',
          },
        },
      },
    },
  },
  plugins: [],
}

