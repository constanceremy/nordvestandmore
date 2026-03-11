import { getEvents } from "@/lib/notion";
import Link from "next/link";
import { MapPin, ArrowRight } from "lucide-react";
import EventFilters from "@/components/EventFilters";
import { Suspense } from "react";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Events | NV & more",
  description: "What's on in Nordvest, Copenhagen. Browse upcoming events, workshops, walks and more.",
  openGraph: {
    title: "Events | NV & more",
    description: "What's on in Nordvest, Copenhagen.",
  },
};

export const revalidate = 3600;

function getDateRangeForPeriod(period: string): { from: string; to: string } | null {
  const cph = { timeZone: "Europe/Copenhagen" };
  const now = new Date();
  const todayStr = now.toLocaleDateString("sv-SE", cph);

  if (period === "today") {
    return { from: todayStr, to: todayStr };
  }

  // Week: Monday–Sunday
  const day = now.getDay(); // 0=Sun
  const offsetToMonday = day === 0 ? -6 : 1 - day;

  if (period === "this-week") {
    const mon = new Date(now); mon.setDate(now.getDate() + offsetToMonday);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { from: mon.toLocaleDateString("sv-SE", cph), to: sun.toLocaleDateString("sv-SE", cph) };
  }

  if (period === "next-week") {
    const mon = new Date(now); mon.setDate(now.getDate() + offsetToMonday + 7);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { from: mon.toLocaleDateString("sv-SE", cph), to: sun.toLocaleDateString("sv-SE", cph) };
  }

  return null;
}

function formatTime(dateStr: string) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-DK", { hour: "2-digit", minute: "2-digit" });
}

function formatDateShort(dateStr: string) {
  if (!dateStr) return { month: "", day: "", weekday: "" };
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { month: "", day: String(dateStr), weekday: "" };
  return {
    month: d.toLocaleDateString("en-DK", { month: "short" }),
    day: String(d.getDate()),
    weekday: d.toLocaleDateString("en-DK", { weekday: "short" }),
  };
}

export default async function EventsPage({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string; location?: string; period?: string; month?: string }>;
}) {
  const params = await searchParams;
  const events = await getEvents(true);

  // Build filter options from real data
  const allTags = [...new Set(events.flatMap((e) => e.tags))].filter(Boolean).sort();
  const allLocations = [...new Set(events.map((e) => e.location))].filter(Boolean).sort();

  // Resolve date range from period or month
  const dateRange = params.period
    ? getDateRangeForPeriod(params.period)
    : params.month
    ? { from: `${params.month}-01`, to: `${params.month}-31` }
    : null;

  // Apply filters
  const filtered = events.filter((e) => {
    if (params.tag && !e.tags.includes(params.tag)) return false;
    if (params.location && e.location !== params.location) return false;
    if (dateRange) {
      const eventDate = e.date?.split("T")[0] ?? "";
      if (eventDate < dateRange.from || eventDate > dateRange.to) return false;
    }
    return true;
  });

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          What's on
        </p>
        <h1 className="text-5xl md:text-7xl" style={{ fontFamily: "DM Serif Display, serif" }}>
          Events
        </h1>
      </div>

      {/* Filters */}
      <Suspense>
        <EventFilters tags={allTags} locations={allLocations} />
      </Suspense>


      {filtered.length === 0 ? (
        <p className="text-gray-400">No events match your filters.</p>
      ) : (
        <div className="divide-y divide-black">
          {filtered.map((event) => {
            const spotsLeft = event.maxSpots - event.bookedSpots;
            const soldOut = event.maxSpots > 0 && spotsLeft <= 0;
            const { month, day, weekday } = formatDateShort(event.date);

            const sharedClass = "group grid grid-cols-[80px_1fr_auto] md:grid-cols-[100px_1fr_200px_auto] items-center gap-6 py-8 hover:bg-black hover:text-white transition-colors px-2 -mx-2";

            return event.ownEvent ? (
              <Link
                key={event.id}
                href={`/events/${event.slug}`}
                className={sharedClass}
              >
                {/* Date */}
                <div className="text-center">
                  <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 group-hover:text-gray-300">
                    {month}
                  </p>
                  <p className="text-4xl font-bold leading-none">{day}</p>
                  <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">
                    {weekday}
                  </p>
                  {formatTime(event.date) && (
                    <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">
                      {formatTime(event.date)}
                    </p>
                  )}
                </div>

                {/* Info */}
                <div className="min-w-0">
                  {event.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-1">
                      {event.tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="text-xs font-semibold tracking-widest uppercase border border-current px-2 py-0.5">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <h2 className="text-xl md:text-2xl font-medium mt-1 leading-snug">
                    {event.title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-gray-500 group-hover:text-gray-300">
                    {event.location && (
                      <span className="flex items-center gap-1">
                        <MapPin size={12} />
                        {event.location}
                      </span>
                    )}
                  </div>
                </div>

                {/* Price + spots */}
                <div className="hidden md:block text-right">
                  {event.price > 0 ? (
                    <p className="text-xl font-bold">{event.price} {event.currency}</p>
                  ) : null}
                  {event.maxSpots > 0 && (
                    <p className={`text-xs mt-1 ${
                      soldOut ? "text-red-500 group-hover:text-red-300"
                      : spotsLeft <= 5 ? "text-amber-500 group-hover:text-amber-300"
                      : "text-gray-400 group-hover:text-gray-300"
                    }`}>
                      {soldOut ? "Sold out" : `${spotsLeft} spots left`}
                    </p>
                  )}
                </div>

                <ArrowRight size={16} className="flex-shrink-0" />
              </Link>
            ) : (
              <a
                key={event.id}
                href={event.notionUrl || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className={sharedClass}
              >
                {/* Date */}
                <div className="text-center">
                  <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 group-hover:text-gray-300">
                    {month}
                  </p>
                  <p className="text-4xl font-bold leading-none">{day}</p>
                  <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">
                    {weekday}
                  </p>
                  {formatTime(event.date) && (
                    <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">
                      {formatTime(event.date)}
                    </p>
                  )}
                </div>
                {/* Info */}
                <div className="min-w-0">
                  {event.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-1">
                      {event.tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="text-xs font-semibold tracking-widest uppercase border border-current px-2 py-0.5">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <h2 className="text-xl md:text-2xl font-medium mt-1 leading-snug">
                    {event.title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-gray-500 group-hover:text-gray-300">
                    {event.location && (
                      <span className="flex items-center gap-1">
                        <MapPin size={12} />
                        {event.location}
                      </span>
                    )}
                  </div>
                </div>
                {/* Price + spots */}
                <div className="hidden md:block text-right">
                  {event.price > 0 ? (
                    <p className="text-xl font-bold">{event.price} {event.currency}</p>
                  ) : null}
                  {event.maxSpots > 0 && (
                    <p className={`text-xs mt-1 ${
                      soldOut ? "text-red-500 group-hover:text-red-300"
                      : spotsLeft <= 5 ? "text-amber-500 group-hover:text-amber-300"
                      : "text-gray-400 group-hover:text-gray-300"
                    }`}>
                      {soldOut ? "Sold out" : `${spotsLeft} spots left`}
                    </p>
                  )}
                </div>
                <ArrowRight size={16} className="flex-shrink-0" />
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
