export type ParsedSearchQuery = {
  song: string;
  artist: string;
};

const QUERY_SEPARATORS = [/\s+—\s+/, /\s+–\s+/, /\s+-\s+/] as const;

export function parseSearchQuery(query: string): ParsedSearchQuery | null {
  const trimmed = query.trim();
  if (!trimmed) {
    return null;
  }

  for (const separator of QUERY_SEPARATORS) {
    const parts = trimmed.split(separator);
    if (parts.length !== 2) {
      continue;
    }

    const song = parts[0]?.trim() ?? "";
    const artist = parts[1]?.trim() ?? "";
    if (song && artist) {
      return { song, artist };
    }
  }

  return null;
}
