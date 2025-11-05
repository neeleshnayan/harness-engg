import forms from '@tailwindcss/forms';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#05070f',
        foreground: '#f5f7ff',
        accent: '#6366f1',
        accentSoft: '#818cf8',
        surface: 'rgba(15,23,42,0.65)',
      },
      boxShadow: {
        glow: '0 10px 40px -12px rgba(99,102,241,0.45)',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['"Inter"', 'sans-serif'],
      },
      keyframes: {
        'pulse-border': {
          '0%, 100%': {
            borderColor: 'rgba(96, 165, 250, 0.5)',
            boxShadow: '0 0 0 0 rgba(96, 165, 250, 0.4)',
          },
          '50%': {
            borderColor: 'rgba(96, 165, 250, 0.8)',
            boxShadow: '0 0 20px 5px rgba(96, 165, 250, 0.3)',
          },
        },
        'success-flash': {
          '0%': {
            borderColor: 'rgba(74, 222, 128, 0.2)',
            backgroundColor: 'rgba(74, 222, 128, 0.05)',
          },
          '50%': {
            borderColor: 'rgba(74, 222, 128, 0.8)',
            backgroundColor: 'rgba(74, 222, 128, 0.2)',
            boxShadow: '0 0 25px 8px rgba(74, 222, 128, 0.4)',
          },
          '100%': {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            backgroundColor: 'transparent',
          },
        },
        'shimmer': {
          '0%': {
            backgroundPosition: '-1000px 0',
          },
          '100%': {
            backgroundPosition: '1000px 0',
          },
        },
      },
      animation: {
        'pulse-border': 'pulse-border 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'success-flash': 'success-flash 1s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
      },
    },
  },
  plugins: [forms],
};
