"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, useMemo, Suspense } from "react";
import Link from "next/link";

type SearchItem = {
  type: "blog" | "own-event" | "event";
  title: string;
  description: string;
  date: string;
  location: string;
  tags: string[];
  url: string;
  external: boolean;
};

function score(item: SearchItem, q: string): number {
  const lower = q.toLowerCase();
  const title = item.title.toLowerCase();
  const desc = item.description.toLowerCase();
  const loc = item.location.toLowerCase();
  const tags = item.tags.join(" ").toLowerCase();
  if (title.startsWith(lower)) return 3;
  if (title.includes(lower)) return 2;
  if (desc.includes(lower) || loc.includes(lower) || tags.includes(lower)) return 1;
  return 0;
}

function formatDate(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-DK", { day: "numeric", month: "short", year: "numeric" });
}

const TABS = ["Events", "Blog"] as const;
type Tab = (typeof TABS)[number];

function SearchResults() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get("q")?.trim() ?? "";
  const tab: Tab = searchParams.get("tab") === "Blog" ? "Blog" : "Events";

  const [index, setIndex] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/search")
      .then((r) => r.json())
      .then((data) => { setIndex(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const { events, blog } = useMemo(() => {
    if (!query || query.length < 2) return { events: [], blog: [] };
    const scored = index.map((item) => ({ item, s: score(item, query) })).filter(({ s }) => s > 0);
    const events = scored
      .filter(({ item }) => item.type === "event" || item.type === "own-event")
      .sort((a, b) => {
        if (a.item.date && b.item.date) return a.item.date.localeCompare(b.item.date);
        return b.s - a.s;
      })
      .map(({ item }) => item);
    const blog = scored
      .filter(({ item }) => item.type === "blog")
      .sort((a, b) => b.s - a.s)
      .map(({ item }) => item);
    return { events, blog };
  }, [index, query]);

  const results = tab === "Events" ? events : blog;

  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-10 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">Search</p>
        <h1
          className="text-4xl md:text-6xl"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          {query ? `"${query}"` : "Search"}
        </h1>
        {!loading && query && (
          <p className="text-sm text-gray-400 mt-3">
            {events.length} event{events.length !== 1 ? "s" : ""} · {blog.length} article{blog.length !== 1 ? "s" : ""}
          </p>
        )}
      </div>

      {!query ? (
        <p className="text-gray-400">Enter a search term to find events and articles.</p>
      ) : loading ? (
        <p className="text-xs text-gray-400 tracking-widest uppercase">Loading…</p>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex border-b border-black mb-8">
            {TABS.map((t) => (
              <Link
                key={t}
                href={`/search?q=${encodeURIComponent(query)}&tab=${t}`}
                className={`text-xs tracking-[0.2em] uppercase px-6 py-3 border-r border-black transition-colors ${
                  tab === t ? "bg-black text-white" : "hover:bg-gray-50"
                }`}
              >
                {t} ({t === "Events" ? events.length : blog.length})
              </Link>
            ))}
          </div>

          {results.length === 0 ? (
            <p className="text-gray-400">No {tab === "Events" ? "events" : "articles"} found for &ldquo;{query}&rdquo;.</p>
          ) : (
            <div className="divide-y divide-black border-t border-black">
              {results.map((item, i) => (
                <Link
                  key={i}
                  href={item.url}
                  target={item.external ? "_blank" : undefined}
                  rel={item.external ? "noopener noreferrer" : undefined}
                  className="flex flex-col md:flex-row md:items-start gap-2 md:gap-8 py-5 hover:opacity-60 transition-opacity"
                >
                  <div className="md:w-32 shrink-0 text-xs text-gray-400 pt-0.5">
                    {formatDate(item.date)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium leading-snug">{item.title}</p>
                    {item.location && (
                      <p className="text-xs text-gray-400 mt-0.5">{item.location}</p>
                    )}
                    {item.type === "blog" && item.description && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{item.description}</p>
                    )}
                  </div>
                  {item.type === "own-event" && (
                    <span className="text-xs tracking-widest uppercase border border-black px-2 py-0.5 self-start shrink-0">
                      NV & more
                    </span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="max-w-4xl mx-auto px-6 py-16 text-xs text-gray-400 tracking-widest uppercase">Loading…</div>}>
      <SearchResults />
    </Suspense>
  );
}
