import { TRACK_MEDIA_ENDPOINT } from "@/lib/api/config";
import type { TrackMediaRequestItem, TrackMediaResponseBody } from "@/types/api";

export async function fetchTrackMedia(
  tracks: TrackMediaRequestItem[],
): Promise<TrackMediaResponseBody["tracks"]> {
  if (tracks.length === 0) {
    return [];
  }

  const response = await fetch(TRACK_MEDIA_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tracks }),
  });

  if (!response.ok) {
    return [];
  }

  try {
    const body = (await response.json()) as TrackMediaResponseBody;
    return body.tracks ?? [];
  } catch {
    return [];
  }
}
