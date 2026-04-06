"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { MapPin, ArrowRight } from "lucide-react";
import type { EventItem } from "@/lib/notion";

function getDateRangeForPeriod(period: string): { from: string; to: string } | null {
  const cph = { timeZone: "Europe/Copenhagen" };
  const now = new Date();
  const todayStr = now.toLocaleDateString("sv-SE", cph);

  if (period === "today") return { from: todayStr, to: todayStr };

  const day = now.getDay();
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
  if (!dateStr.includes("T")) return "All day";
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

export default function EventList({ events }: { events: EventItem[] }) {
  const searchParams = useSearchParams();
  const tag = searchParams.get("tag") || "";
  const location = searchParams.get("location") || "";
  const period = searchParams.get("period") || "";
  const month = searchParams.get("month") || "";

  // Always filter to today or future using the browser's real current date,
  // so stale ISR cache never shows past events.
  const todayStr = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });

  const dateRange = period
    ? getDateRangeForPeriod(period)
    : month
    ? { from: `${month}-01`, to: `${month}-31` }
    : null;

  const filtered = events.filter((e) => {
    const eventDate = e.date?.split("T")[0] ?? "";
    if (eventDate && eventDate < todayStr) return false;
    if (tag && !e.tags.includes(tag)) return false;
    if (location && e.location !== location) return false;
    if (dateRange) {
      if (eventDate < dateRange.from || eventDate > dateRange.to) return false;
    }
    return true;
  }).sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""));

  if (filtered.length === 0) {
    return <p className="text-gray-400">No events match your filters.</p>;
  }

  const sharedClass =
    "group grid grid-cols-[80px_1fr_auto] md:grid-cols-[100px_1fr_200px_auto] items-center gap-6 py-8 hover:bg-black hover:text-white transition-colors px-2 -mx-2";

  return (
    <div className="divide-y divide-black">
      {filtered.map((event) => {
        const spotsLeft = event.maxSpots - event.bookedSpots;
        const soldOut = event.maxSpots > 0 && spotsLeft <= 0;
        const { month: mo, day, weekday } = formatDateShort(event.date);
        const time = formatTime(event.date);

        const dateBox = (
          <div className="text-center">
            <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 group-hover:text-gray-300">{mo}</p>
            <p className="text-4xl font-bold leading-none">{day}</p>
            <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">{weekday}</p>
            {time && <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">{time}</p>}
          </div>
        );

        const infoBox = (
          <div className="min-w-0">
            {event.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-1">
                {event.tags.slice(0, 2).map((t) => (
                  <span key={t} className="text-xs font-semibold tracking-widest uppercase border border-current px-2 py-0.5">{t}</span>
                ))}
              </div>
            )}
            <h2 className="text-xl md:text-2xl font-medium mt-1 leading-snug">{event.title}</h2>
            {event.location && (
              <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-gray-500 group-hover:text-gray-300">
                <span className="flex items-center gap-1"><MapPin size={12} />{event.location}</span>
              </div>
            )}
          </div>
        );

        const priceBox = (
          <div className="hidden md:block text-right">
            {event.price > 0 && <p className="text-xl font-bold">{event.price} {event.currency}</p>}
            {event.maxSpots > 0 && (
              <p className={`text-xs mt-1 ${soldOut ? "text-red-500 group-hover:text-red-300" : spotsLeft <= 5 ? "text-amber-500 group-hover:text-amber-300" : "text-gray-400 group-hover:text-gray-300"}`}>
                {soldOut ? "Sold out" : `${spotsLeft} spots left`}
              </p>
            )}
          </div>
        );

        return event.ownEvent ? (
          <Link key={event.id} href={`/events/${event.slug}`} className={sharedClass}>
            {dateBox}{infoBox}{priceBox}
            <ArrowRight size={16} className="flex-shrink-0" />
          </Link>
        ) : (
          <a key={event.id} href={event.notionUrl || "#"} target="_blank" rel="noopener noreferrer" className={sharedClass}>
            {dateBox}{infoBox}{priceBox}
            <ArrowRight size={16} className="flex-shrink-0" />
          </a>
        );
      })}
    </div>
  );
}
