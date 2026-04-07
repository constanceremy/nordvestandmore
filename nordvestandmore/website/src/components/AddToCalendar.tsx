"use client";

import { useState, useRef, useEffect } from "react";
import { CalendarPlus } from "lucide-react";

type Props = {
  title: string;
  date: string;        // ISO date string or "YYYY-MM-DD"
  startTime?: string;  // "10:00am" or "10:00" — if omitted, extracted from date if it has a time component
  endTime?: string;
  location?: string;
  description?: string;
  compact?: boolean;   // icon only, no label
};

function parseTime(t?: string): { h: number; m: number } | null {
  if (!t) return null;
  const match = t.match(/(\d+):(\d+)\s*(am|pm)?/i);
  if (!match) return null;
  let h = parseInt(match[1]);
  const m = parseInt(match[2]);
  const period = match[3]?.toLowerCase();
  if (period === "pm" && h !== 12) h += 12;
  if (period === "am" && h === 12) h = 0;
  return { h, m };
}

function extractTimeFromISO(iso: string): { h: number; m: number } | null {
  if (!iso.includes("T")) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  // Use Copenhagen local time
  const local = new Date(d.toLocaleString("sv-SE", { timeZone: "Europe/Copenhagen" }));
  return { h: local.getHours(), m: local.getMinutes() };
}

function toIcsDate(dateStr: string, time?: { h: number; m: number }): string {
  const base = dateStr.includes("T") ? dateStr : `${dateStr}T00:00:00`;
  const d = new Date(new Date(base).toLocaleString("sv-SE", { timeZone: "Europe/Copenhagen" }));
  const y = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  if (!time) return `${y}${mo}${day}`;
  const h = String(time.h).padStart(2, "0");
  const m = String(time.m).padStart(2, "0");
  return `${y}${mo}${day}T${h}${m}00`;
}

export default function AddToCalendar({ title, date, startTime, endTime, location, description, compact }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const start = parseTime(startTime) ?? extractTimeFromISO(date) ?? undefined;
  const end = parseTime(endTime) ?? (start ? { h: start.h + 1, m: start.m } : undefined);

  const startFmt = toIcsDate(date, start);
  const endFmt = toIcsDate(date, end);

  const googleUrl = new URL("https://calendar.google.com/calendar/render");
  googleUrl.searchParams.set("action", "TEMPLATE");
  googleUrl.searchParams.set("text", title);
  googleUrl.searchParams.set("dates", `${startFmt}/${endFmt}`);
  if (location) googleUrl.searchParams.set("location", location);
  if (description) googleUrl.searchParams.set("details", description);

  function downloadIcs() {
    const allDay = !start;
    const dtStart = allDay ? `DTSTART;VALUE=DATE:${startFmt}` : `DTSTART;TZID=Europe/Copenhagen:${startFmt}`;
    const dtEnd = allDay ? `DTEND;VALUE=DATE:${endFmt}` : `DTEND;TZID=Europe/Copenhagen:${endFmt}`;
    const ics = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//NV & more//EN",
      "BEGIN:VEVENT",
      dtStart,
      dtEnd,
      `SUMMARY:${title}`,
      location ? `LOCATION:${location}` : "",
      description ? `DESCRIPTION:${description.replace(/\n/g, "\\n")}` : "",
      "END:VEVENT",
      "END:VCALENDAR",
    ].filter(Boolean).join("\r\n");

    const blob = new Blob([ics], { type: "text/calendar" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[^a-z0-9]/gi, "-").toLowerCase()}.ics`;
    a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v); }}
        className={`flex items-center gap-2 text-xs tracking-[0.15em] uppercase border border-current bg-white text-black group-hover:bg-black group-hover:text-white transition-colors ${
          compact ? "p-2" : "px-4 py-2.5"
        }`}
        aria-label="Add to calendar"
        title="Add to calendar"
      >
        <CalendarPlus size={13} />
        {!compact && "Add to calendar"}
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 z-20 bg-white text-black border border-black min-w-[180px]">
          <a
            href={googleUrl.toString()}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
            className="block px-4 py-3 text-xs tracking-[0.15em] uppercase hover:bg-black hover:text-white transition-colors border-b border-black"
          >
            Google Calendar
          </a>
          <button
            onClick={(e) => { e.stopPropagation(); downloadIcs(); }}
            className="w-full text-left px-4 py-3 text-xs tracking-[0.15em] uppercase hover:bg-black hover:text-white transition-colors"
          >
            Apple / iCal
          </button>
        </div>
      )}
    </div>
  );
}
