export type RecommendRequestBody = {
  song: string;
  artist: string;
};

export type ApiQuery = {
  song: string;
  artist: string;
};

export type ApiRecommendationItem = {
  rank: number;
  artist: string;
  song: string;
  score: number;
  youtube?: string;
  cover?: string;
};

export type RecommendResponseBody = {
  success: boolean;
  query?: ApiQuery;
  recommendations?: ApiRecommendationItem[];
  error?: string;
  message?: string;
};

export type TrackMediaRequestItem = {
  song: string;
  artist: string;
};

export type TrackMediaResponseItem = {
  song: string;
  artist: string;
  youtube: string;
  cover: string;
};

export type TrackMediaResponseBody = {
  tracks: TrackMediaResponseItem[];
};
