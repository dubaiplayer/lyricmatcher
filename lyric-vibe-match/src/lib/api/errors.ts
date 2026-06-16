export class RecommendApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "RecommendApiError";
  }
}

export function getRecommendErrorMessage(error: unknown): string {
  if (error instanceof RecommendApiError) {
    return error.message;
  }
  if (error instanceof TypeError) {
    return "Unable to reach the recommendation server. Check that the backend is running.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}
