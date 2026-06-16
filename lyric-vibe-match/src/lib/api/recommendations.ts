import { RECOMMEND_ENDPOINT } from "@/lib/api/config";
import { RecommendApiError } from "@/lib/api/errors";
import type { RecommendRequestBody, RecommendResponseBody } from "@/types/api";

function extractErrorMessage(body: RecommendResponseBody, status: number): string {
  return (
    body.error ??
    body.message ??
    `Recommendation request failed (${status}).`
  );
}

export async function fetchRecommendations(
  song: string,
  artist: string,
): Promise<RecommendResponseBody> {
  const payload: RecommendRequestBody = { song, artist };

  let response: Response;
  try {
    response = await fetch(RECOMMEND_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new RecommendApiError(
      "Unable to reach the recommendation server. Check that the backend is running.",
    );
  }

  let body: RecommendResponseBody;
  try {
    body = (await response.json()) as RecommendResponseBody;
  } catch {
    throw new RecommendApiError(
      response.ok
        ? "Received an invalid response from the server."
        : `Recommendation request failed (${response.status}).`,
      response.status,
    );
  }

  if (!response.ok) {
    throw new RecommendApiError(extractErrorMessage(body, response.status), response.status);
  }

  return body;
}
