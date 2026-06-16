import type { ApiRecommendationItem } from "@/types/api";
import type { Recommendation } from "@/types/recommendation";

/** Centralized UI placeholders until the API returns rich metadata. */
export const RECOMMENDATION_UI_PLACEHOLDERS = {
  album: "—",
  year: 0,
  cover:
    "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=600&q=80",
  reason: "Matched on lyrics, themes, and emotional tone.",
  themes: ["Lyrics", "Mood", "Themes"] as const,
} as const;

function buildYoutubeFallbackUrl(song: string, artist: string): string {
  const q = encodeURIComponent(`${song} ${artist}`.trim());
  return `https://www.youtube.com/embed?listType=search&list=${q}&autoplay=1`;
}

export function scoreToMatchPercent(score: number): number {
  if (score > 1) {
    return Math.round(Math.min(score, 100));
  }
  return Math.round(Math.min(Math.max(score, 0), 1) * 100);
}

export function mapApiRecommendationToUi(item: ApiRecommendationItem): Recommendation {
  const { album, year, cover, reason, themes } = RECOMMENDATION_UI_PLACEHOLDERS;

  return {
    id: String(item.rank),
    song: item.song,
    artist: item.artist,
    album,
    year,
    cover: item.cover ?? cover,
    youtube: item.youtube ?? buildYoutubeFallbackUrl(item.song, item.artist),
    themes: [...themes],
    match: scoreToMatchPercent(item.score),
    reason,
  };
}

export function mapApiRecommendationsToUi(items: ApiRecommendationItem[]): Recommendation[] {
  return [...items].sort((a, b) => a.rank - b.rank).map(mapApiRecommendationToUi);
}
