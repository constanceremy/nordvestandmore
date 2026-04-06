"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { X, Search } from "lucide-react";

type SearchItem = {
  type: "blog" | "own-event" | "event";
  title: string;
  description: string;
  date: string;
  location: string;
  url: string;
  external: boolean;
};

const TYPE_LABEL: Record<string, string> = {
  blog: "Blog",
  "own-event": "Our events",
  event: "Events",
};

function formatDate(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-DK", { day: "numeric", month: "short", year: "numeric" });
}

function score(item: SearchItem, q: string): number {
  const lower = q.toLowerCase();
  const title = item.title.toLowerCase();
  const desc = item.description.toLowerCase();
  const loc = item.location.toLowerCase();
  if (title.startsWith(lower)) return 3;
  if (title.includes(lower)) return 2;
  if (desc.includes(lower) || loc.includes(lower)) return 1;
  return 0;
}

export default function SearchModal({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    inputRef.current?.focus();
    fetch("/api/search")
      .then((r) => r.json())
      .then((data) => { setIndex(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const results = query.trim().length < 2
    ? []
    : index
        .map((item) => ({ item, s: score(item, query.trim()) }))
        .filter(({ s }) => s > 0)
        .sort((a, b) => b.s - a.s)
        .slice(0, 12)
        .map(({ item }) => item);

  // Group results
  const grouped = results.reduce<Record<string, SearchItem[]>>((acc, item) => {
    const key = TYPE_LABEL[item.type] ?? item.type;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  const groupOrder = ["Blog", "Our events", "Events"];

  const navigate = useCallback((item: SearchItem) => {
    onClose();
    if (item.external) {
      window.open(item.url, "_blank", "noopener noreferrer");
    } else {
      router.push(item.url);
    }
  }, [onClose, router]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed top-24 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl px-4">
        <div className="bg-white border border-black flex flex-col max-h-[70vh]">
          {/* Input */}
          <form
            className="flex items-center gap-3 px-4 py-4 border-b border-black"
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim().length >= 2) {
                router.push(`/search?q=${encodeURIComponent(query.trim())}`);
                onClose();
              }
            }}
          >
            <Search size={16} className="text-gray-400 shrink-0" />
            <input
              ref={inputRef}
              type="search"
              placeholder="Search events, blog posts..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 text-sm tracking-wide outline-none placeholder:text-gray-400 bg-transparent"
            />
            <button type="button" onClick={onClose} className="hover:opacity-50 transition-opacity">
              <X size={16} />
            </button>
          </form>

          {/* Results */}
          <div className="overflow-y-auto">
            {loading && (
              <p className="text-xs text-gray-400 px-4 py-6 tracking-widest uppercase">Loading…</p>
            )}
            {!loading && query.trim().length >= 2 && results.length === 0 && (
              <p className="text-xs text-gray-400 px-4 py-6 tracking-widest uppercase">No results</p>
            )}
            {!loading && query.trim().length < 2 && (
              <p className="text-xs text-gray-400 px-4 py-6 tracking-widest uppercase">Type to search</p>
            )}
            {groupOrder.map((group) => {
              const items = grouped[group];
              if (!items?.length) return null;
              return (
                <div key={group}>
                  <p className="text-xs tracking-[0.25em] uppercase text-gray-400 px-4 pt-4 pb-2 border-b border-gray-100">
                    {group}
                  </p>
                  {items.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => navigate(item)}
                      className="w-full text-left px-4 py-3 hover:bg-black hover:text-white transition-colors border-b border-gray-100 last:border-0 group"
                    >
                      <p className="text-sm font-medium leading-snug">{item.title}</p>
                      <div className="flex items-center gap-3 mt-0.5">
                        {item.date && (
                          <span className="text-xs text-gray-400 group-hover:text-gray-300">
                            {formatDate(item.date)}
                          </span>
                        )}
                        {item.location && (
                          <span className="text-xs text-gray-400 group-hover:text-gray-300">
                            {item.location}
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
