"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { EventItem, BlogPost } from "@/lib/notion";

const PAGE_SIZE = 8;

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", { day: "numeric", month: "short" }).toUpperCase();
}

function formatTime(iso: string) {
  if (!iso || !iso.includes("T")) return "";
  return new Date(iso).toLocaleTimeString("en-DK", { hour: "2-digit", minute: "2-digit" });
}

export default function LocationTabs({
  events,
  posts,
}: {
  events: EventItem[];
  posts: BlogPost[];
}) {
  const [tab, setTab] = useState<"events" | "articles">(events.length > 0 ? "events" : "articles");
  const [eventCount, setEventCount] = useState(PAGE_SIZE);

  const visibleEvents = events.slice(0, eventCount);
  const remainingEvents = events.length - eventCount;

  if (events.length === 0 && posts.length === 0) {
    return (
      <p className="text-xs tracking-[0.2em] uppercase text-gray-400">
        No events or articles linked yet.
      </p>
    );
  }

  return (
    <div>
      {/* Tabs */}
      <div className="flex border-b border-black mb-0">
        {events.length > 0 && (
          <button
            onClick={() => setTab("events")}
            className={`text-xs tracking-[0.2em] uppercase px-4 py-3 border-r border-black transition-colors ${
              tab === "events" ? "bg-black text-white" : "hover:bg-gray-50"
            }`}
          >
            Events ({events.length})
          </button>
        )}
        {posts.length > 0 && (
          <button
            onClick={() => setTab("articles")}
            className={`text-xs tracking-[0.2em] uppercase px-4 py-3 transition-colors ${
              tab === "articles" ? "bg-black text-white" : "hover:bg-gray-50"
            }`}
          >
            Articles ({posts.length})
          </button>
        )}
      </div>

      {/* Events tab */}
      {tab === "events" && (
        <div>
          <div className="divide-y divide-black">
            {visibleEvents.map((event) => (
              <div key={event.id} className="group relative flex items-center justify-between gap-4 py-3 hover:bg-black hover:text-white transition-colors px-2 -mx-2">
                {event.ownEvent ? (
                  <Link href={`/events/${event.slug}`} className="absolute inset-0" aria-label={event.title} />
                ) : (
                  <a href={event.notionUrl || "#"} target="_blank" rel="noopener noreferrer" className="absolute inset-0" aria-label={event.title} />
                )}
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex-shrink-0 w-10">
                    <p className="text-xs text-gray-400 group-hover:text-gray-300 leading-none">{formatDate(event.date)}</p>
                    {formatTime(event.date) && <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">{formatTime(event.date)}</p>}
                  </div>
                  <p className="text-sm font-medium truncate">{event.title}</p>
                </div>
                <ArrowRight size={12} className="flex-shrink-0 pointer-events-none" />
              </div>
            ))}
          </div>
          {remainingEvents > 0 && (
            <button
              onClick={() => setEventCount((c) => c + PAGE_SIZE)}
              className="mt-4 text-xs tracking-[0.15em] uppercase border border-black px-4 py-2 hover:bg-black hover:text-white transition-colors"
            >
              Load more ({remainingEvents} remaining)
            </button>
          )}
        </div>
      )}

      {/* Articles tab */}
      {tab === "articles" && (
        <div className="divide-y divide-black">
          {posts.map((post) => (
            <Link
              key={post.id}
              href={`/blog/${post.slug}`}
              className="group flex items-center justify-between gap-4 py-3 hover:bg-black hover:text-white transition-colors px-2 -mx-2"
            >
              <p className="text-sm font-medium leading-snug">{post.title}</p>
              <ArrowRight size={12} className="flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
