import { getEvents, getBlogPosts } from "@/lib/notion";
import type { EventItem, BlogPost } from "@/lib/notion";
import Link from "next/link";
import type { Metadata } from "next";

export const revalidate = 3600;

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const { q } = await searchParams;
  return { title: q ? `"${q}" — Search | NV & more` : "Search | NV & more" };
}

function scoreEvent(e: EventItem, q: string): number {
  const lower = q.toLowerCase();
  if (e.title.toLowerCase().startsWith(lower)) return 3;
  if (e.title.toLowerCase().includes(lower)) return 2;
  if (
    e.description?.toLowerCase().includes(lower) ||
    e.location?.toLowerCase().includes(lower) ||
    e.organizer?.toLowerCase().includes(lower)
  ) return 1;
  return 0;
}

function scoreBlog(p: BlogPost, q: string): number {
  const lower = q.toLowerCase();
  if (p.title.toLowerCase().startsWith(lower)) return 3;
  if (p.title.toLowerCase().includes(lower)) return 2;
  if (p.excerpt?.toLowerCase().includes(lower)) return 1;
  return 0;
}

function formatDate(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-DK", { day: "numeric", month: "short", year: "numeric" });
}

const TAB_LABELS = ["Events", "Blog"] as const;
type Tab = (typeof TAB_LABELS)[number];

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; tab?: string }>;
}) {
  const { q, tab: tabParam } = await searchParams;
  const query = q?.trim() ?? "";
  const tab: Tab = tabParam === "Blog" ? "Blog" : "Events";

  const [allEvents, allPosts] = await Promise.all([getEvents(true), getBlogPosts()]);

  const matchedEvents = query.length < 2
    ? []
    : allEvents
        .map((e) => ({ e, s: scoreEvent(e, query) }))
        .filter(({ s }) => s > 0)
        .sort((a, b) => {
          // Primary: date ascending; secondary: relevance score
          if (a.e.date && b.e.date) return a.e.date.localeCompare(b.e.date);
          return b.s - a.s;
        })
        .map(({ e }) => e);

  const matchedPosts = query.length < 2
    ? []
    : allPosts
        .map((p) => ({ p, s: scoreBlog(p, query) }))
        .filter(({ s }) => s > 0)
        .sort((a, b) => b.s - a.s)
        .map(({ p }) => p);

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
        {query && (
          <p className="text-sm text-gray-400 mt-3">
            {matchedEvents.length} event{matchedEvents.length !== 1 ? "s" : ""} · {matchedPosts.length} article{matchedPosts.length !== 1 ? "s" : ""}
          </p>
        )}
      </div>

      {!query ? (
        <p className="text-gray-400">Enter a search term to find events and articles.</p>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex border-b border-black mb-8">
            {TAB_LABELS.map((t) => (
              <Link
                key={t}
                href={`/search?q=${encodeURIComponent(query)}&tab=${t}`}
                className={`text-xs tracking-[0.2em] uppercase px-6 py-3 border-r border-black transition-colors ${
                  tab === t ? "bg-black text-white" : "hover:bg-gray-50"
                }`}
              >
                {t} ({t === "Events" ? matchedEvents.length : matchedPosts.length})
              </Link>
            ))}
          </div>

          {/* Events tab */}
          {tab === "Events" && (
            <>
              {matchedEvents.length === 0 ? (
                <p className="text-gray-400">No events found for &ldquo;{query}&rdquo;.</p>
              ) : (
                <div className="divide-y divide-black border-t border-black">
                  {matchedEvents.map((e) => {
                    const href = e.ownEvent ? `/events/${e.slug}` : e.notionUrl;
                    const isExternal = !e.ownEvent;
                    return (
                      <Link
                        key={e.id}
                        href={href}
                        target={isExternal ? "_blank" : undefined}
                        rel={isExternal ? "noopener noreferrer" : undefined}
                        className="flex flex-col md:flex-row md:items-start gap-2 md:gap-8 py-5 hover:opacity-60 transition-opacity"
                      >
                        <div className="md:w-32 shrink-0 text-xs text-gray-400 pt-0.5">
                          {e.date && !e.date.includes("T")
                            ? formatDate(e.date)
                            : e.date
                            ? new Date(e.date).toLocaleDateString("en-DK", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })
                            : ""}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium leading-snug">{e.title}</p>
                          {e.location && (
                            <p className="text-xs text-gray-400 mt-0.5">{e.location}</p>
                          )}
                        </div>
                        {e.ownEvent && (
                          <span className="text-xs tracking-widest uppercase border border-black px-2 py-0.5 self-start shrink-0">
                            NV & more
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* Blog tab */}
          {tab === "Blog" && (
            <>
              {matchedPosts.length === 0 ? (
                <p className="text-gray-400">No articles found for &ldquo;{query}&rdquo;.</p>
              ) : (
                <div className="divide-y divide-black border-t border-black">
                  {matchedPosts.map((p) => (
                    <Link
                      key={p.id}
                      href={`/blog/${p.slug}`}
                      className="flex flex-col md:flex-row md:items-start gap-2 md:gap-8 py-5 hover:opacity-60 transition-opacity"
                    >
                      <div className="md:w-32 shrink-0 text-xs text-gray-400 pt-0.5">
                        {formatDate(p.publishedDate)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium leading-snug">{p.title}</p>
                        {p.excerpt && (
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{p.excerpt}</p>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
