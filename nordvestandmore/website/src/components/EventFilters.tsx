"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useState, useRef, useEffect } from "react";
import { SlidersHorizontal, X, ChevronDown } from "lucide-react";

type Props = {
  tags: string[];
  locations: string[];
};

const PERIODS = [
  { label: "Today", value: "today" },
  { label: "This week", value: "this-week" },
  { label: "Next week", value: "next-week" },
];

function getUpcomingMonths(count = 6) {
  const months = [];
  const now = new Date();
  for (let i = 0; i < count; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    months.push({
      label: d.toLocaleDateString("en-DK", { month: "short", year: "numeric" }).toUpperCase(),
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
    });
  }
  return months;
}

type LocationComboboxProps = {
  locations: string[];
  selected: string;
  onSelect: (loc: string) => void;
  className?: string;
};

function LocationCombobox({ locations, selected, onSelect, className = "" }: LocationComboboxProps) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = locations.filter((l) =>
    l.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div ref={ref} className={`relative ${className}`}>
      <div className="flex items-center border border-black">
        <input
          type="text"
          placeholder="Search location..."
          value={open ? search : selected || ""}
          onChange={(e) => { setSearch(e.target.value); setOpen(true); }}
          onFocus={() => { setSearch(""); setOpen(true); }}
          className="text-xs tracking-[0.15em] uppercase px-4 py-2 flex-1 outline-none placeholder:normal-case placeholder:tracking-normal placeholder:text-gray-400 bg-transparent min-w-0"
        />
        {selected && (
          <button
            onMouseDown={(e) => { e.preventDefault(); onSelect(""); setSearch(""); setOpen(false); }}
            className="px-2 hover:opacity-50"
          >
            <X size={12} />
          </button>
        )}
        <ChevronDown size={12} className="mr-3 text-gray-400 shrink-0" />
      </div>
      {open && filtered.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-30 bg-white border border-t-0 border-black max-h-48 overflow-y-auto">
          {filtered.map((l) => (
            <button
              key={l}
              onMouseDown={(e) => { e.preventDefault(); onSelect(l === selected ? "" : l); setSearch(""); setOpen(false); }}
              className={`w-full text-left text-xs tracking-[0.15em] uppercase px-4 py-2.5 hover:bg-black hover:text-white transition-colors ${
                selected === l ? "bg-black text-white" : ""
              }`}
            >
              {l}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function EventFilters({ tags, locations }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const tag = searchParams.get("tag") || "";
  const location = searchParams.get("location") || "";
  const period = searchParams.get("period") || "";
  const month = searchParams.get("month") || "";

  const setParam = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams]
  );

  const togglePeriod = (val: string) =>
    setParam({ period: period === val ? "" : val, month: "" });

  const toggleMonth = (val: string) =>
    setParam({ month: month === val ? "" : val, period: "" });

  const hasFilters = !!(tag || location || period || month);
  const months = getUpcomingMonths();

  const whenSelectValue = period ? `period:${period}` : month ? `month:${month}` : "";

  const handleWhenSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) setParam({ period: "", month: "" });
    else if (val.startsWith("period:")) setParam({ period: val.slice(7), month: "" });
    else setParam({ month: val.slice(6), period: "" });
  };

  return (
    <>
      {/* Mobile: trigger button */}
      <div className="md:hidden mb-8">
        <button
          onClick={() => setDrawerOpen(true)}
          className="flex items-center gap-2 text-xs tracking-[0.2em] uppercase border border-black px-4 py-3 hover:bg-black hover:text-white transition-colors"
        >
          <SlidersHorizontal size={12} />
          Filter events
          {hasFilters && <span className="w-1.5 h-1.5 rounded-full bg-black" />}
        </button>
        {hasFilters && (
          <div className="flex flex-wrap gap-2 mt-3">
            {period && (
              <span className="text-xs tracking-[0.15em] uppercase bg-black text-white px-3 py-1">
                {PERIODS.find((p) => p.value === period)?.label}
              </span>
            )}
            {month && (
              <span className="text-xs tracking-[0.15em] uppercase bg-black text-white px-3 py-1">
                {months.find((m) => m.value === month)?.label}
              </span>
            )}
            {tag && <span className="text-xs tracking-[0.15em] uppercase bg-black text-white px-3 py-1">{tag}</span>}
            {location && <span className="text-xs tracking-[0.15em] uppercase bg-black text-white px-3 py-1">{location}</span>}
          </div>
        )}
      </div>

      {/* Desktop: inline */}
      <div className="hidden md:block mb-10 border-b border-black pb-10">
        <div className="space-y-6">
          {/* When — all pills on one line */}
          <div>
            <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">When</p>
            <div className="flex flex-wrap gap-2">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => togglePeriod(p.value)}
                  className={`text-xs tracking-[0.15em] uppercase px-4 py-2 border transition-colors ${
                    period === p.value
                      ? "bg-black text-white border-black"
                      : "border-black hover:bg-black hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
              {months.map((m) => (
                <button
                  key={m.value}
                  onClick={() => toggleMonth(m.value)}
                  className={`text-xs tracking-[0.15em] uppercase px-4 py-2 border transition-colors ${
                    month === m.value
                      ? "bg-black text-white border-black"
                      : "border-gray-300 hover:border-black"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Type */}
          {tags.length > 0 && (
            <div>
              <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">Type</p>
              <div className="flex flex-wrap gap-2">
                {tags.map((t) => (
                  <button
                    key={t}
                    onClick={() => setParam({ tag: tag === t ? "" : t })}
                    className={`text-xs tracking-[0.15em] uppercase px-4 py-2 border transition-colors ${
                      tag === t
                        ? "bg-black text-white border-black"
                        : "border-black hover:bg-black hover:text-white"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Location — searchable combobox */}
          {locations.length > 0 && (
            <div>
              <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">Location</p>
              <LocationCombobox
                locations={locations}
                selected={location}
                onSelect={(l) => setParam({ location: l })}
                className="w-72"
              />
            </div>
          )}

          {hasFilters && (
            <button
              onClick={() => router.push(pathname)}
              className="text-xs tracking-[0.2em] uppercase underline underline-offset-4 hover:opacity-50 transition-opacity"
            >
              Clear all filters
            </button>
          )}
        </div>
      </div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <>
          <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setDrawerOpen(false)} />
          <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-black p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-8">
              <p className="text-xs tracking-[0.3em] uppercase font-semibold">Filter events</p>
              <button onClick={() => setDrawerOpen(false)}><X size={16} /></button>
            </div>

            <div className="space-y-8">
              {/* When — dropdown */}
              <div>
                <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">When</p>
                <div className="relative">
                  <select
                    value={whenSelectValue}
                    onChange={handleWhenSelect}
                    className="w-full text-xs tracking-[0.15em] uppercase border border-black px-4 py-3 appearance-none bg-white outline-none pr-8"
                  >
                    <option value="">Any time</option>
                    {PERIODS.map((p) => (
                      <option key={p.value} value={`period:${p.value}`}>{p.label}</option>
                    ))}
                    {months.map((m) => (
                      <option key={m.value} value={`month:${m.value}`}>{m.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={12} className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Type */}
              {tags.length > 0 && (
                <div>
                  <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">Type</p>
                  <div className="flex flex-wrap gap-2">
                    {tags.map((t) => (
                      <button
                        key={t}
                        onClick={() => setParam({ tag: tag === t ? "" : t })}
                        className={`text-xs tracking-[0.15em] uppercase px-4 py-2 border transition-colors ${
                          tag === t
                            ? "bg-black text-white border-black"
                            : "border-black hover:bg-black hover:text-white"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Location — searchable combobox */}
              {locations.length > 0 && (
                <div>
                  <p className="text-xs tracking-[0.25em] uppercase text-gray-400 mb-3">Location</p>
                  <LocationCombobox
                    locations={locations}
                    selected={location}
                    onSelect={(l) => { setParam({ location: l }); }}
                  />
                </div>
              )}

              {hasFilters && (
                <button
                  onClick={() => { router.push(pathname); setDrawerOpen(false); }}
                  className="text-xs tracking-[0.2em] uppercase underline underline-offset-4 hover:opacity-50 transition-opacity"
                >
                  Clear all filters
                </button>
              )}
            </div>

            <button
              onClick={() => setDrawerOpen(false)}
              className="w-full mt-8 py-4 bg-black text-white text-xs tracking-[0.2em] uppercase"
            >
              Show results
            </button>
          </div>
        </>
      )}
    </>
  );
}
