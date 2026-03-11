import { getEvents, getBlogPosts } from "@/lib/notion";
import Link from "next/link";
import { ArrowRight, MapPin } from "lucide-react";

export const revalidate = 3600;

function formatDateLabel(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d
    .toLocaleDateString("en-DK", { day: "numeric", month: "short" })
    .toUpperCase();
}

function formatTimeLabel(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-DK", { hour: "2-digit", minute: "2-digit" });
}

function isToday(iso: string) {
  if (!iso) return false;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });
  const eventDate = new Date(iso).toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });
  return eventDate === today;
}

export default async function Home() {
  const [events, posts] = await Promise.all([
    getEvents(true).catch(() => []),
    getBlogPosts().catch(() => []),
  ]);

  const todayEvents = events
    .filter((e) => isToday(e.date))
    .sort((a, b) => a.date.localeCompare(b.date));
  const hasToday = todayEvents.length > 0;
  const displayEvents = hasToday ? todayEvents : events.slice(0, 6); // show all today's, cap fallback at 6
  const sectionLabel = hasToday ? "Today in Nordvest" : "Next in Nordvest";
  const latestPosts = posts.slice(0, 3);

  return (
    <div>
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-20 border-b border-black">
        <h1
          className="text-[clamp(4rem,14vw,12rem)] leading-[0.9] mb-10 -ml-1 font-thin tracking-tight"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          NV<br />
          &amp; more
        </h1>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-8">
          <p className="text-sm tracking-[0.2em] uppercase text-gray-500 max-w-xs leading-relaxed">
            Events, guides and stories from Copenhagen's most vibrant neighbourhood
          </p>
          <Link
            href="/events"
            className="inline-flex items-center gap-3 text-xs tracking-[0.25em] uppercase border border-black px-8 py-4 hover:bg-black hover:text-white transition-colors self-start sm:self-auto"
          >
            See all events <ArrowRight size={12} />
          </Link>
        </div>
      </section>

      {/* ── Upcoming Events ───────────────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="flex items-baseline justify-between border-b border-black pb-5 mb-2">
          <p className="text-xs tracking-[0.3em] uppercase">
            {sectionLabel}
          </p>
          <Link
            href="/events"
            className="text-xs tracking-[0.2em] uppercase hover:underline underline-offset-4"
          >
            All events →
          </Link>
        </div>

        {displayEvents.length === 0 ? (
          <p className="text-xs tracking-[0.2em] uppercase text-gray-400 py-12">
            No upcoming events — check back soon
          </p>
        ) : (
          <div className="divide-y divide-black">
            {displayEvents.map((event) => (
              <a
                key={event.id}
                href={event.notionUrl || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="group grid grid-cols-[72px_1fr_auto] md:grid-cols-[72px_120px_1fr_200px_auto] items-baseline gap-4 md:gap-8 py-6 hover:bg-black hover:text-white transition-colors px-2 -mx-2"
              >
                <span className="text-xs tracking-[0.2em] uppercase text-gray-400 group-hover:text-gray-300 leading-relaxed">
                  {formatDateLabel(event.date)}
                  {formatTimeLabel(event.date) && (
                    <><br />{formatTimeLabel(event.date)}</>
                  )}
                </span>
                <span className="text-xs tracking-[0.15em] uppercase text-gray-400 group-hover:text-gray-300 hidden md:block truncate">
                  {event.tags[0] || "—"}
                </span>
                <span className="text-xl md:text-2xl leading-none tracking-tight truncate">
                  {event.title}
                </span>
                {event.location && (
                  <span className="text-xs tracking-[0.15em] uppercase text-gray-400 group-hover:text-gray-300 hidden md:flex items-center gap-1 truncate">
                    <MapPin size={10} />
                    {event.location}
                  </span>
                )}
                <ArrowRight size={14} className="shrink-0" />
              </a>
            ))}
          </div>
        )}
      </section>

      {/* ── Blog ──────────────────────────────────────────────────────────── */}
      {latestPosts.length > 0 && (
        <section className="max-w-6xl mx-auto px-6 py-16 border-t border-black">
          <div className="flex items-baseline justify-between border-b border-black pb-5 mb-8">
            <p className="text-xs tracking-[0.3em] uppercase">
              From the blog
            </p>
            <Link
              href="/blog"
              className="text-xs tracking-[0.2em] uppercase hover:underline underline-offset-4"
            >
              All posts →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-black border border-black">
            {latestPosts.map((post) => (
              <Link
                key={post.id}
                href={`/blog/${post.slug}`}
                className="group bg-white p-8 hover:bg-black hover:text-white transition-colors flex flex-col"
              >
                {post.coverImage ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={post.coverImage}
                    alt={post.title}
                    className="w-full h-48 object-cover grayscale mb-6"
                  />
                ) : (
                  <div className="w-full h-48 bg-gray-100 mb-6 flex items-center justify-center border border-gray-200 group-hover:border-gray-700">
                    <span className="text-3xl text-gray-300" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>NV</span>
                  </div>
                )}
                <p className="text-xs tracking-[0.25em] uppercase text-gray-400 group-hover:text-gray-300 mb-3">
                  {post.tags[0] ? `${post.tags[0]} | ` : ""}
                  {new Date(post.publishedDate)
                    .toLocaleDateString("en-DK", { month: "short", year: "numeric" })
                    .toUpperCase()}
                </p>
                <h2 className="text-xl leading-snug tracking-tight flex-1 mb-3">
                  {post.title}
                </h2>
                {post.excerpt && (
                  <p className="text-xs tracking-[0.1em] uppercase text-gray-500 group-hover:text-gray-300 line-clamp-2 leading-relaxed">
                    {post.excerpt}
                  </p>
                )}
                <p className="text-xs tracking-[0.25em] uppercase mt-5 underline underline-offset-4">
                  Read →
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ── No blog yet placeholder ───────────────────────────────────────── */}
      {latestPosts.length === 0 && (
        <section className="max-w-6xl mx-auto px-6 py-16 border-t border-black">
          <div className="flex items-baseline justify-between border-b border-black pb-5 mb-8">
            <p className="text-xs tracking-[0.3em] uppercase">
              From the blog
            </p>
          </div>
          <p className="text-xs tracking-[0.2em] uppercase text-gray-400 py-12">
            Coming soon
          </p>
        </section>
      )}
    </div>
  );
}
