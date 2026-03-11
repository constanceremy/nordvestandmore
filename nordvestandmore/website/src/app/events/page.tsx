import { getEvents } from "@/lib/notion";
import EventFilters from "@/components/EventFilters";
import EventList from "@/components/EventList";
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

export default async function EventsPage() {
  const events = await getEvents(true);

  const allTags = [...new Set(events.flatMap((e) => e.tags))].filter(Boolean).sort();
  const allLocations = [...new Set(events.map((e) => e.location))].filter(Boolean).sort();

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          What's on
        </p>
        <h1 className="text-5xl md:text-7xl" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
          Events
        </h1>
      </div>

      <Suspense>
        <EventFilters tags={allTags} locations={allLocations} />
      </Suspense>

      <Suspense fallback={<p className="text-gray-400">Loading events…</p>}>
        <EventList events={events} />
      </Suspense>
    </div>
  );
}
