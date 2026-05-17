"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowRight, X, Search } from "lucide-react";
import type { LocationItem } from "@/lib/notion";

const GuideMap = dynamic(() => import("@/components/GuideMap"), { ssr: false });

const TAG_ORDER = [
  "cafe", "coffee", "food", "bakery", "restaurant", "takeout",
  "bar", "drink", "wine", "natural wine", "beer", "brewery",
  "wellness", "sauna", "health", "yoga", "sport", "swimming",
  "shop", "groceries", "market", "design",
  "outdoor", "park", "green space", "nature",
  "culture", "community", "library", "art", "theatre", "music", "workshop",
];

export default function MapClient({ locations }: { locations: LocationItem[] }) {
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const allTags = useMemo(() => {
    const tagSet = new Set(locations.flatMap((l) => l.tags));
    const ordered = TAG_ORDER.filter((t) => tagSet.has(t));
    const rest = [...tagSet].filter((t) => !TAG_ORDER.includes(t)).sort();
    return [...ordered, ...rest];
  }, [locations]);

  const matchingTags = useMemo(() => {
    if (!query) return allTags;
    const lower = query.toLowerCase();
    return allTags.filter((t) => t.includes(lower));
  }, [allTags, query]);

  const filtered = useMemo(() => {
    let result = locations;
    if (activeTag) result = result.filter((l) => l.tags.includes(activeTag));
    if (query && !activeTag) {
      const lower = query.toLowerCase();
      result = result.filter(
        (l) =>
          l.name.toLowerCase().includes(lower) ||
          l.tags.some((t) => t.toLowerCase().includes(lower))
      );
    }
    return result;
  }, [locations, activeTag, query]);

  return (
    <>
      {/* Header strip */}
      <div className="max-w-6xl mx-auto px-6 pt-12 pb-6">
        <p className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-2">NV & more</p>
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-6">
          <h1
            className="text-5xl md:text-7xl font-thin leading-none tracking-tight -ml-1"
            style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
          >
            The Map
          </h1>
          <p className="text-sm tracking-[0.15em] uppercase text-gray-500 max-w-sm">
            Every spot we love in Nordvest
          </p>
        </div>

        {/* Search + tag filters */}
        <div className="space-y-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActiveTag(null); }}
              placeholder="Search spots or tags..."
              className="w-full border border-black pl-9 pr-9 py-2.5 text-sm tracking-wide placeholder:text-gray-400 outline-none focus:bg-gray-50"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-black"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => { setActiveTag(null); setQuery(""); }}
              className={`text-xs tracking-[0.15em] uppercase px-3 py-1.5 border transition-colors ${
                !activeTag && !query ? "bg-black text-white border-black" : "border-black hover:bg-black hover:text-white"
              }`}
            >
              All
            </button>
            {matchingTags.map((tag) => (
              <button
                key={tag}
                onClick={() => { setActiveTag(activeTag === tag ? null : tag); setQuery(""); }}
                className={`text-xs tracking-[0.15em] uppercase px-3 py-1.5 border transition-colors ${
                  activeTag === tag ? "bg-black text-white border-black" : "border-black hover:bg-black hover:text-white"
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Full-width map — the hero */}
      <div className="border-y border-black isolate">
        <div className="h-[65vh] min-h-[480px] max-h-[800px]">
          <GuideMap locations={filtered} />
        </div>
      </div>

      {/* Result count + scannable list */}
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="flex items-baseline justify-between mb-6 border-b border-black pb-3">
          <h2 className="text-xs font-semibold tracking-[0.3em] uppercase text-gray-400">
            {filtered.length} spot{filtered.length !== 1 ? "s" : ""}
            {activeTag ? ` · ${activeTag}` : ""}
          </h2>
          {(activeTag || query) && (
            <button
              onClick={() => { setActiveTag(null); setQuery(""); }}
              className="text-xs tracking-[0.2em] uppercase underline underline-offset-4 hover:opacity-50"
            >
              Clear
            </button>
          )}
        </div>

        {filtered.length === 0 ? (
          <p className="text-gray-400 text-xs tracking-[0.2em] uppercase py-12 text-center">
            No spots match.
          </p>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-black border border-black">
            {filtered.map((loc) => (
              <li key={loc.id} className="bg-white">
                <Link
                  href={`/map/${loc.slug}`}
                  className="group flex items-center justify-between gap-4 px-5 py-4 h-full hover:bg-black hover:text-white transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-1 mb-1">
                      {loc.tags.slice(0, 3).map((t) => (
                        <span key={t} className="text-[10px] tracking-[0.15em] uppercase text-gray-400 group-hover:text-gray-300">
                          {t}
                        </span>
                      ))}
                    </div>
                    <p className="text-base font-medium leading-snug truncate">{loc.name}</p>
                  </div>
                  <ArrowRight size={14} className="flex-shrink-0 opacity-50 group-hover:opacity-100" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
