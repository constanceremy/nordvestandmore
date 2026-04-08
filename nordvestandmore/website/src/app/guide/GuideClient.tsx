"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowRight, X } from "lucide-react";
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

export default function GuideClient({ locations }: { locations: LocationItem[] }) {
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  // Collect all tags that appear in the data, in preferred order
  const allTags = useMemo(() => {
    const tagSet = new Set(locations.flatMap((l) => l.tags));
    const ordered = TAG_ORDER.filter((t) => tagSet.has(t));
    const rest = [...tagSet].filter((t) => !TAG_ORDER.includes(t)).sort();
    return [...ordered, ...rest];
  }, [locations]);

  // Tags matching the search query (for filtered pill suggestions)
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
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="border-b border-black pb-8 mb-8">
        <p className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-2">NV & more</p>
        <h1
          className="text-5xl md:text-7xl font-thin leading-tight tracking-tight -ml-1"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          The Guide
        </h1>
        <p className="text-sm tracking-[0.15em] uppercase text-gray-500 mt-4 max-w-sm">
          Our favourite spots in Nordvest
        </p>
      </div>

      {/* Search + tag filters */}
      <div className="mb-8 space-y-3">
        {/* Search input */}
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveTag(null); }}
            placeholder="Search spots or tags..."
            className="w-full border border-black px-4 py-2.5 text-sm tracking-wide placeholder:text-gray-400 outline-none focus:bg-gray-50"
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

        {/* Tag pills — filtered by search query */}
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

      {/* Map + List split */}
      <div className="flex flex-col lg:flex-row gap-0 border border-black">
        {/* Map */}
        <div className="lg:w-1/2 h-[400px] lg:h-auto lg:min-h-[600px] border-b lg:border-b-0 lg:border-r border-black">
          <GuideMap locations={filtered} />
        </div>

        {/* List */}
        <div className="lg:w-1/2 divide-y divide-black overflow-y-auto lg:max-h-[600px]">
          {filtered.length === 0 && (
            <p className="text-gray-400 text-xs tracking-[0.2em] uppercase p-8">No spots match.</p>
          )}
          {filtered.map((loc) => (
            <Link
              key={loc.id}
              href={`/guide/${loc.slug}`}
              className="group flex items-center justify-between gap-4 px-6 py-4 hover:bg-black hover:text-white transition-colors"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap gap-1 mb-1">
                  {loc.tags.slice(0, 3).map((t) => (
                    <span key={t} className="text-xs tracking-[0.1em] uppercase text-gray-400 group-hover:text-gray-300">
                      {t}
                    </span>
                  ))}
                </div>
                <p className="text-lg font-medium leading-snug truncate">{loc.name}</p>
              </div>
              <ArrowRight size={14} className="flex-shrink-0" />
            </Link>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-400 tracking-[0.1em] uppercase mt-4">
        {filtered.length} spot{filtered.length !== 1 ? "s" : ""}
        {activeTag ? ` tagged "${activeTag}"` : " in Nordvest"}
      </p>
    </div>
  );
}
