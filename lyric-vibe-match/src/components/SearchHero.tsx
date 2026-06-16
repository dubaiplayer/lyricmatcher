import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";

type Props = {
  onSearch: (query: string) => void | Promise<void>;
  isLoading: boolean;
};

export function SearchHero({ onSearch, isLoading }: Props) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <section className="relative overflow-hidden px-6 pt-24 pb-12 md:pt-36 md:pb-20">
      <div className="mx-auto max-w-3xl text-center">
        <div className="mb-5 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
          <span className="h-1 w-1 rounded-full bg-primary animate-pulse-glow" />
          Listen Now
        </div>

        <h1 className="font-display text-5xl font-bold leading-[1.02] tracking-tight md:text-7xl">
          Personalized <span className="text-gradient">feel</span>
          <br /> songs.
        </h1>

        <p className="mx-auto mt-5 max-w-lg text-[15px] text-muted-foreground md:text-base">
          Type in the song to find perfect recommendations.
        </p>

        <form onSubmit={handleSubmit} className="mx-auto mt-10 max-w-xl">
          <div className="group relative flex items-center gap-2 rounded-full border border-border bg-surface/80 px-2 py-2 backdrop-blur-xl transition-all focus-within:border-primary/60 focus-within:bg-surface-elevated">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted-foreground">
              <Search className="h-[18px] w-[18px]" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search a song or artist…"
              className="flex-1 bg-transparent py-2 text-[15px] text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="hidden h-9 items-center gap-2 rounded-full bg-primary px-5 text-[13px] font-semibold text-primary-foreground transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 sm:inline-flex"
            >
              {isLoading ? "Listening…" : "Find matches"}
            </button>
          </div>
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="mt-3 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground disabled:opacity-40 sm:hidden"
          >
            {isLoading ? "Listening…" : "Find matches"}
          </button>
        </form>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
          <span className="opacity-60">Try</span>
          {["4 Wheeler - Yuno Miles", "Plastic Bag - Yuno Miles", "Ray Gun - Yuno Miles"].map((s) => (
            <button
              key={s}
              onClick={() => {
                setQuery(s);
                onSearch(s);
              }}
              className="rounded-full border border-border bg-surface/40 px-3 py-1 text-foreground/80 transition-colors hover:border-primary/40 hover:text-foreground"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
