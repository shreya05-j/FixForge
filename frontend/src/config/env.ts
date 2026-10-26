/**
 * Centralized Application & API Environment Configuration
 * Softcoded to import.meta.env.VITE_API_BASE_URL with intelligent browser-origin fallback.
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.hostname
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://localhost:8000');
