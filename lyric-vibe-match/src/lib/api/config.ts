export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

export const RECOMMEND_ENDPOINT = `${API_BASE_URL}/api/recommend`;
export const TRACK_MEDIA_ENDPOINT = `${API_BASE_URL}/api/track-media`;
