import { useEffect, useState } from "react";
import { Play, MoreHorizontal } from "lucide-react";
import type { Recommendation } from "@/types/recommendation";
import { RECOMMENDATION_UI_PLACEHOLDERS } from "@/lib/recommendationPlaceholders";

export function RecommendationCard({ rec, index }: { rec: Recommendation; index: number }) {
  const [coverSrc, setCoverSrc] = useState(rec.cover);

  useEffect(() => {
    setCoverSrc(rec.cover);
  }, [rec.cover]);

  return (
    <article className="group relative flex flex-col gap-3">
      {/* Album cover */}
      <a
        href={rec.youtube}
        target="_blank"
        rel="noopener noreferrer"
        className="relative aspect-square overflow-hidden rounded-lg bg-surface shadow-card"
        aria-label={`Play ${rec.song} on YouTube`}
      >
        <img
          src={coverSrc}
          alt={`${rec.song} by ${rec.artist} cover`}
          loading="lazy"
          onError={() => setCoverSrc(RECOMMENDATION_UI_PLACEHOLDERS.cover)}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
        />

        {/* Hover dim */}
        <div className="absolute inset-0 bg-black/0 transition-colors duration-300 group-hover:bg-black/30" />

        {/* Match badge */}
        <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5 rounded-md bg-black/60 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-white backdrop-blur-md">
          <span className="h-1 w-1 rounded-full bg-primary" />
          {rec.match}% MATCH
        </div>

        {/* Rank */}
        <div className="absolute right-2.5 top-2.5 font-display text-xs font-bold tabular-nums text-white/90 drop-shadow">
          #{index + 1}
        </div>

        {/* Play button */}
        <div className="absolute bottom-2.5 right-2.5 flex h-11 w-11 translate-y-2 items-center justify-center rounded-full bg-primary text-primary-foreground opacity-0 shadow-glow transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
          <Play className="h-5 w-5 fill-current" />
        </div>
      </a>

      {/* Info — Apple Music style: minimal, tight, two lines */}
      <div className="flex items-start justify-between gap-2 px-0.5">
        <a
          href={rec.youtube}
          target="_blank"
          rel="noopener noreferrer"
          className="min-w-0 flex-1"
          aria-label={`Play ${rec.song} by ${rec.artist} on YouTube`}
        >
          <h3 className="truncate text-[15px] font-semibold leading-tight text-foreground transition-colors hover:text-primary">
            {rec.song}
          </h3>
          <p className="mt-0.5 truncate text-[13px] text-muted-foreground">
            {rec.artist}
          </p>
        </a>
        <button
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-muted-foreground opacity-0 transition-all hover:bg-surface-elevated hover:text-foreground group-hover:opacity-100"
          aria-label="More options"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>

      {/* Reason — subtle, only on hover area */}
      <div className="px-0.5">
        <p className="line-clamp-2 text-[12px] leading-relaxed text-muted-foreground/80">
          {rec.reason}
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          {rec.themes.slice(0, 3).map((t) => (
            <span
              key={t}
              className="rounded-md bg-surface px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}
