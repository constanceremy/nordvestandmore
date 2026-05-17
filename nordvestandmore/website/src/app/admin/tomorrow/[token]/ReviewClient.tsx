"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { ReviewEvent } from "@/lib/review";
import { ExternalLink, ChevronDown, ChevronRight } from "lucide-react";

type Props = {
  token: string;
  date: string;
  singletons: ReviewEvent[];
  duplicates: ReviewEvent[][];
};

type MergeStatus = "idle" | "loading" | "merged" | "error";

export default function ReviewClient({ token, date, singletons, duplicates: initialDuplicates }: Props) {
  const router = useRouter();
  const [showSingletons, setShowSingletons] = useState(false);
  const [statuses, setStatuses] = useState<Record<number, MergeStatus>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [, startTransition] = useTransition();

  function setStatus(idx: number, s: MergeStatus) {
    setStatuses((p) => ({ ...p, [idx]: s }));
  }

  async function handleMerge(clusterIdx: number, ids: string[]) {
    setStatus(clusterIdx, "loading");
    try {
      const r = await fetch("/api/admin/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, eventIds: ids }),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setErrors((p) => ({ ...p, [clusterIdx]: data.error || `HTTP ${r.status}` }));
        setStatus(clusterIdx, "error");
        return;
      }
      setStatus(clusterIdx, "merged");
    } catch (e) {
      setErrors((p) => ({ ...p, [clusterIdx]: (e as Error).message }));
      setStatus(clusterIdx, "error");
    }
  }

  function navigateDate(deltaDays: number) {
    const d = new Date(date);
    d.setUTCDate(d.getUTCDate() + deltaDays);
    const iso = d.toISOString().slice(0, 10);
    startTransition(() => {
      router.push(`/admin/tomorrow/${token}?date=${iso}`);
    });
  }

  function pickDate(value: string) {
    if (!value) return;
    startTransition(() => {
      router.push(`/admin/tomorrow/${token}?date=${value}`);
    });
  }

  const total = singletons.length + initialDuplicates.reduce((s, c) => s + c.length, 0);
  const dateObj = new Date(date);
  const dayLabel = dateObj.toLocaleDateString("en-DK", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="border-b border-black pb-6 mb-8">
        <p className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-2">Admin · Daily review</p>
        <h1
          className="text-4xl md:text-5xl font-thin leading-tight"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          {dayLabel}
        </h1>
        <p className="text-sm text-gray-600 mt-3">
          {total} event{total !== 1 ? "s" : ""} · {singletons.length} unique · {initialDuplicates.length} cluster{initialDuplicates.length !== 1 ? "s" : ""} to review
        </p>

        {/* Date controls */}
        <div className="flex items-center gap-3 mt-5">
          <button
            onClick={() => navigateDate(-1)}
            className="text-xs tracking-[0.15em] uppercase border border-black px-3 py-2 hover:bg-black hover:text-white transition-colors"
          >
            ← Prev day
          </button>
          <input
            type="date"
            value={date}
            onChange={(e) => pickDate(e.target.value)}
            className="text-xs tracking-[0.15em] uppercase border border-black px-3 py-2"
          />
          <button
            onClick={() => navigateDate(1)}
            className="text-xs tracking-[0.15em] uppercase border border-black px-3 py-2 hover:bg-black hover:text-white transition-colors"
          >
            Next day →
          </button>
        </div>
      </div>

      {/* Duplicates */}
      {initialDuplicates.length === 0 ? (
        <div className="border border-black px-6 py-8 mb-12 text-center">
          <p className="text-sm tracking-[0.15em] uppercase">
            🎉 No duplicate clusters detected for this day.
          </p>
        </div>
      ) : (
        <div className="space-y-6 mb-12">
          {initialDuplicates.map((cluster, idx) => {
            const status = statuses[idx] || "idle";
            return (
              <div
                key={idx}
                className={`border border-black ${status === "merged" ? "opacity-40" : ""}`}
              >
                <div className="border-b border-black px-5 py-3 flex items-center justify-between gap-4">
                  <p className="text-xs tracking-[0.2em] uppercase">
                    Cluster {idx + 1} · {cluster.length} events
                  </p>
                  {status === "merged" && (
                    <p className="text-xs tracking-[0.2em] uppercase">✓ Merged</p>
                  )}
                </div>

                <ul className="divide-y divide-black">
                  {cluster.map((ev) => {
                    const link = ev.eventLink || ev.sourceUrl;
                    const tagShown = ev.tagList.length ? ev.tagList : ev.tagsLegacy;
                    const tagLabel = ev.tagList.length ? "Tag List" : ev.tagsLegacy.length ? "Tags (legacy)" : null;
                    const truncatedTitle = ev.title.length > 200 ? ev.title.slice(0, 200) + "…" : ev.title;
                    return (
                      <li key={ev.id} className="px-5 py-4">
                        <p className="font-medium leading-snug mb-1">{truncatedTitle || "(no title)"}</p>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
                          {ev.startTime && <span>⏰ {ev.startTime}</span>}
                          {ev.location && <span>📍 {ev.location}</span>}
                          {ev.sourceType && <span>📡 {ev.sourceType}</span>}
                        </div>
                        {tagShown && tagShown.length > 0 && (
                          <p className="text-xs text-gray-500 mt-1">
                            🏷 {tagLabel}: {tagShown.join(", ")}
                          </p>
                        )}
                        <div className="flex flex-wrap gap-3 mt-2 text-xs">
                          <a
                            href={ev.notionUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 tracking-[0.15em] uppercase underline underline-offset-4 hover:opacity-50"
                          >
                            Open in Notion <ExternalLink size={10} />
                          </a>
                          {link && (
                            <a
                              href={link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 tracking-[0.15em] uppercase text-gray-500 underline underline-offset-4 hover:text-black"
                            >
                              Source link <ExternalLink size={10} />
                            </a>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>

                <div className="border-t border-black px-5 py-4 flex flex-wrap items-center gap-3">
                  {status === "merged" ? (
                    <p className="text-sm">Merged. Refresh to remove from list.</p>
                  ) : status === "loading" ? (
                    <p className="text-sm">Merging…</p>
                  ) : (
                    <>
                      <button
                        onClick={() => handleMerge(idx, cluster.map((e) => e.id))}
                        className="text-xs tracking-[0.2em] uppercase bg-black text-white px-5 py-2.5 hover:bg-gray-900 disabled:opacity-50"
                        disabled={status !== "idle" && status !== "error"}
                      >
                        Merge
                      </button>
                      <button
                        onClick={() => setStatus(idx, "merged")}
                        className="text-xs tracking-[0.2em] uppercase border border-black px-5 py-2.5 hover:bg-black hover:text-white"
                      >
                        Skip
                      </button>
                      {status === "error" && (
                        <p className="text-xs text-red-600">{errors[idx] || "Error"}</p>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Singletons (collapsed by default) */}
      <div className="border-t border-black pt-6">
        <button
          onClick={() => setShowSingletons((v) => !v)}
          className="flex items-center gap-2 text-xs tracking-[0.2em] uppercase hover:opacity-50"
        >
          {showSingletons ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {singletons.length} unique event{singletons.length !== 1 ? "s" : ""}
        </button>
        {showSingletons && (
          <ul className="mt-4 divide-y divide-black border-t border-black">
            {singletons.map((ev) => {
              const truncatedTitle = ev.title.length > 140 ? ev.title.slice(0, 140) + "…" : ev.title;
              const tagShown = ev.tagList.length ? ev.tagList : ev.tagsLegacy;
              return (
                <li key={ev.id} className="py-3">
                  <p className="text-sm font-medium leading-snug">{truncatedTitle || "(no title)"}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mt-1">
                    {ev.startTime && <span>⏰ {ev.startTime}</span>}
                    {ev.location && <span>📍 {ev.location}</span>}
                    {ev.sourceType && <span>📡 {ev.sourceType}</span>}
                    {tagShown.length > 0 && <span>🏷 {tagShown.join(", ")}</span>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
