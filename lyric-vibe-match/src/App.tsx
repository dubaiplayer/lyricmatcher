import { useCallback, useState } from "react";
import { Disc3, RotateCcw } from "lucide-react";
import { SearchHero } from "@/components/SearchHero";
import { LoadingState } from "@/components/LoadingState";
import { RecommendationCard } from "@/components/RecommendationCard";
import { fetchRecommendations } from "@/lib/api/recommendations";
import { fetchTrackMedia } from "@/lib/api/trackMedia";
import { getRecommendErrorMessage } from "@/lib/api/errors";
import { parseSearchQuery } from "@/lib/parseSearchQuery";
import { mapApiRecommendationsToUi } from "@/lib/recommendationPlaceholders";
import type { Recommendation } from "@/types/recommendation";
import type { SearchContext } from "@/types/search";

const PARSE_ERROR_MESSAGE =
  'Enter a song and artist separated by " — " or " - " (e.g. Liability — Lorde).';

const EMPTY_RESULTS_MESSAGE =
  "No recommendations found for that track. Try another song or artist.";

const BACKEND_FAILURE_MESSAGE =
  "Could not load recommendations. Please try again.";

function scrollToResults() {
  requestAnimationFrame(() => {
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

export function App() {
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchContext, setSearchContext] = useState<SearchContext | null>(null);

  const handleSearch = useCallback(async (query: string) => {
    setError(null);
    setLoading(true);
    setResults(null);
    setSearchContext(null);

    try {
      const parsed = parseSearchQuery(query);

      if (!parsed) {
        setError(PARSE_ERROR_MESSAGE);
        return;
      }

      const { song, artist } = parsed;
      const response = await fetchRecommendations(song, artist);

      if (!response.success) {
        setError(response.error ?? response.message ?? BACKEND_FAILURE_MESSAGE);
        return;
      }

      const apiItems = response.recommendations ?? [];
      if (apiItems.length === 0) {
        setError(EMPTY_RESULTS_MESSAGE);
        return;
      }

      const context: SearchContext = {
        query,
        song: response.query?.song ?? song,
        artist: response.query?.artist ?? artist,
      };

      setSearchContext(context);
      const uiResults = mapApiRecommendationsToUi(apiItems);
      setResults(uiResults);
      scrollToResults();

      void fetchTrackMedia(
        apiItems.map((item) => ({ song: item.song, artist: item.artist })),
      ).then((tracks) => {
        if (tracks.length === 0) {
          return;
        }
        setResults((prev) => {
          if (!prev) {
            return prev;
          }
          return prev.map((rec) => {
            const media = tracks.find(
              (track) => track.song === rec.song && track.artist === rec.artist,
            );
            if (!media) {
              return rec;
            }
            return { ...rec, cover: media.cover, youtube: media.youtube };
          });
        });
      });
    } catch (err) {
      setError(getRecommendErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = () => {
    setResults(null);
    setError(null);
    setSearchContext(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const showResultsSection =
    searchContext !== null && !loading && !error && results !== null && results.length > 0;

  return (
    <main className="min-h-screen">
      <header className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-6 py-5 md:px-10">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Disc3 className="h-[18px] w-[18px] text-primary-foreground" />
          </div>
          <span className="font-display text-[17px] font-bold tracking-tight">Resonate</span>
        </div>
        <span className="hidden text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground md:block">
          Lyrics · Themes · Emotion
        </span>
      </header>

      <SearchHero onSearch={handleSearch} isLoading={loading} />

      <section id="results" className="px-6 pb-24 md:px-10">
        <div className="mx-auto max-w-7xl">
          {error && !loading && (
            <div
              role="alert"
              className="mx-auto max-w-xl rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-center text-sm text-destructive"
            >
              {error}
            </div>
          )}

          {loading && <LoadingState />}

          {showResultsSection && searchContext && results && (
            <>
              <div className="mb-8 flex flex-col items-start justify-between gap-4 border-t border-border pt-8 md:flex-row md:items-end">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
                    Because you played
                  </p>
                  <h2 className="mt-2 font-display text-3xl font-bold md:text-4xl">
                    {searchContext.song}
                  </h2>
                  <p className="mt-1 text-lg text-muted-foreground">{searchContext.artist}</p>
                  <p className="mt-2 max-w-xl text-[13px] text-muted-foreground">
                    Five tracks matched on lyrical themes, emotional tone, and narrative voice.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={reset}
                  className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-4 py-2 text-[13px] font-medium transition-colors hover:border-primary/60 hover:bg-surface-elevated"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  New search
                </button>
              </div>

              <div
                id="recommendations"
                className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
                aria-live="polite"
              >
                {results.map((rec, index) => (
                  <RecommendationCard key={rec.id} rec={rec} index={index} />
                ))}
              </div>
            </>
          )}
        </div>
      </section>

      <footer className="border-t border-border px-6 py-8 text-center text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        Resonate · Built for music that means something
      </footer>
    </main>
  );
}
