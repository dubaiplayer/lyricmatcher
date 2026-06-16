export function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-24">
      <div className="flex h-12 items-end gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="equalizer-bar w-1 rounded-full bg-primary"
            style={{ animationDelay: `${i * 0.1}s` }}
          />
        ))}
      </div>
      <p className="text-[13px] font-medium tracking-wide text-muted-foreground">
        Finding matches…
      </p>
    </div>
  );
}
