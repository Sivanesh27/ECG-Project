/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0B0B0B', bg: '#111111', panel: '#181818', line: '#2A2A2A',
        orange: { DEFAULT: '#FF6A00', bright: '#FF7A18', dim: '#B34A00' }, muted: '#A0A0A0',
      },
      fontFamily: { sans: ['Barlow', 'system-ui', 'sans-serif'], mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'] },
      borderRadius: { DEFAULT: '2px', md: '3px', lg: '4px' },
    },
  },
  plugins: [],
}
