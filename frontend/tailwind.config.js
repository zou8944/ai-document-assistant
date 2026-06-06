import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        serif: ['"Cormorant Garamond"', 'Georgia', '"Times New Roman"', 'serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
      },
      colors: {
        // Editorial Library palette
        paper: {
          DEFAULT: '#F7F5F0',
          warm: '#F0EDE5',
          dark: '#E8E4D9',
          edge: '#DCD7C8',
        },
        ink: {
          DEFAULT: '#1C1C1E',
          soft: '#3A3A3C',
        },
        muted: {
          DEFAULT: '#8E8E93',
          soft: '#B8B8BD',
        },
        accent: {
          DEFAULT: '#007AFF',
          soft: '#4A9EFF',
          deep: '#0055D4',
          tint: '#E5F2FF',
          'tint-strong': '#CCE5FF',
        },
        sage: {
          DEFAULT: '#7B8B6F',
          soft: '#C5D4B6',
        },
        rust: {
          DEFAULT: '#B5651D',
          soft: '#E8C49A',
        },
        crimson: {
          DEFAULT: '#C73E1D',
          soft: '#E8B4A8',
        },
        // Legacy aliases kept for compatibility during migration
        'macos-blue': '#007AFF',
        'macos-gray': {
          50: '#F9F9F9',
          100: '#F2F2F7',
          200: '#E5E5EA',
          300: '#D1D1D6',
          400: '#C7C7CC',
          500: '#AEAEB2',
          600: '#8E8E93',
          700: '#636366',
          800: '#48484A',
          900: '#1C1C1E',
        },
      },
      borderRadius: {
        'sm-editorial': '8px',
        'md-editorial': '12px',
        'lg-editorial': '16px',
        'xl-editorial': '24px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(28, 28, 30, 0.04), 0 4px 12px rgba(28, 28, 30, 0.05)',
        lift: '0 2px 4px rgba(28, 28, 30, 0.06), 0 12px 32px rgba(28, 28, 30, 0.09)',
        modal: '0 24px 64px rgba(28, 28, 30, 0.18), 0 8px 16px rgba(28, 28, 30, 0.08)',
        accent: '0 6px 20px rgba(0, 122, 255, 0.18)',
      },
      backdropBlur: {
        xs: '2px',
        xl: '20px',
        '2xl': '40px',
        '3xl': '64px',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'breathe': 'breathe 2.8s ease-in-out infinite',
        'drift': 'drift 6s ease-in-out infinite',
        'reveal-up': 'revealUp 0.48s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        breathe: {
          '0%, 100%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.06)' },
        },
        drift: {
          '0%, 100%': { transform: 'translate(0, 0)' },
          '50%': { transform: 'translate(8px, -6px)' },
        },
        revealUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [
    typography,
  ],
}
