/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand: deep forest green
        forest: {
          50: '#F0F7F1',
          100: '#DCEEE1',
          200: '#BBDEC5',
          300: '#8FC7A0',
          400: '#5FAC77',
          500: '#2E7D32',
          600: '#27692B',
          700: '#1F5423',
          800: '#163F1A',
          900: '#0F2A12',
        },
        // Brand: warm earth brown
        earth: {
          50: '#FAF6F2',
          100: '#F3EAE0',
          200: '#E4D1BC',
          300: '#CDAD8C',
          400: '#AC8358',
          500: '#8B5E3C',
          600: '#6D4C41',
          700: '#553B32',
          800: '#3C2A23',
          900: '#291C17',
        },
        // Neutrals: warm black + soft whites
        ink: {
          DEFAULT: '#191817',
          soft: '#44403C',
          mute: '#78716C',
          faint: '#A8A29E',
        },
        cream: '#FAF9F5',
        surface: '#FFFFFF',
        // Workflow status colors (re-themed to match the brand)
        status: {
          pending: '#D97706',
          verified: '#0E7490',
          assigned: '#8B5E3C',
          cleared: '#2E7D32',
        },
        priority: {
          low: '#78716C',
          medium: '#F59E0B',
          high: '#EA580C',
          critical: '#DC2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(25,24,23,0.06), 0 1px 3px rgba(25,24,23,0.08)',
        lift: '0 4px 12px rgba(25,24,23,0.10)',
      },
    },
  },
  plugins: [],
}