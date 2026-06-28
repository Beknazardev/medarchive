import Link from "next/link";
import { SearchX } from "lucide-react";

export function EmptyState({
  title,
  message,
  queries = [],
  target = "/search",
}: {
  title: string;
  message: string;
  queries?: string[];
  target?: "/search" | "/compare";
}) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface)] px-5 py-10 text-center">
      <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--muted-foreground)]">
        <SearchX className="h-5 w-5" aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-base font-semibold text-[var(--foreground)]">{title}</h2>
      <p className="mx-auto mt-1 max-w-lg text-sm text-[var(--muted-foreground)]">{message}</p>
      {queries.length > 0 ? (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {queries.map((query) => (
            <Link
              key={query}
              href={`${target}?q=${encodeURIComponent(query)}`}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-semibold hover:border-[var(--primary)] hover:text-[var(--primary)]"
            >
              {query}
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
