export type Recommendation = {
  id: string;
  song: string;
  artist: string;
  album: string;
  year: number;
  cover: string;
  youtube: string;
  themes: string[];
  match: number;
  reason: string;
};
