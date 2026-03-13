import { getSessions, getPrivateExperiences } from "@/lib/notion";
import Link from "next/link";
import { MapPin, ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import PrivateExperienceSection from "@/components/PrivateExperienceSection";

export const metadata: Metadata = {
  title: "With Us | NV & more",
  description: "Events and experiences led by NV & more — neighbourhood walks and more in Nordvest, Copenhagen.",
  openGraph: {
    title: "With Us | NV & more",
    description: "Events and experiences led by NV & more in Nordvest, Copenhagen.",
  },
};

export const revalidate = 3600;

function formatDateShort(dateStr: string) {
  if (!dateStr) return { month: "", day: "", weekday: "" };
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { month: "", day: "", weekday: "" };
  return {
    month: d.toLocaleDateString("en-DK", { month: "short" }),
    day: String(d.getDate()),
    weekday: d.toLocaleDateString("en-DK", { weekday: "short" }),
  };
}

export default async function WithUsPage() {
  const [sessions, privateExperiences] = await Promise.all([
    getSessions(true),
    getPrivateExperiences(),
  ]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Led by NV & more
        </p>
        <h1 className="text-5xl md:text-7xl" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
          With us
        </h1>
        <p className="mt-6 text-sm text-gray-500 max-w-lg leading-relaxed">
          Events and experiences we run ourselves — in and around Nordvest.
          Spots are limited; book your place below.
        </p>
      </div>

      {sessions.length === 0 ? (
        <p className="text-xs tracking-[0.2em] uppercase text-gray-400 py-12">
          Nothing scheduled right now — check back soon.
        </p>
      ) : (
        <div className="divide-y divide-black">
          {sessions.map((session) => {
            const exp = session.experience;
            if (!exp) return null;

            const price = session.priceOverride ?? exp.price;
            const maxSpots = session.maxSpots || exp.maxSpots;
            const spotsLeft = maxSpots - session.bookedSpots;
            const soldOut = maxSpots > 0 && spotsLeft <= 0;
            const { month, day, weekday } = formatDateShort(session.date);

            const sharedContent = (
              <>
                {/* Date */}
                <div className="text-center">
                  <p className={`text-xs font-semibold tracking-widest uppercase mb-0 ${soldOut ? "text-gray-300" : "text-gray-400 group-hover:text-gray-300"}`}>
                    {month}
                  </p>
                  <p className="text-4xl font-bold leading-none">{day}</p>
                  <p className={`text-xs mt-0.5 ${soldOut ? "text-gray-300" : "text-gray-400 group-hover:text-gray-300"}`}>
                    {weekday}
                  </p>
                  {session.startTime && (
                    <p className={`text-xs mt-0.5 ${soldOut ? "text-gray-300" : "text-gray-400 group-hover:text-gray-300"}`}>
                      {session.startTime}
                    </p>
                  )}
                </div>

                {/* Info */}
                <div className="min-w-0">
                  {exp.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-1">
                      {exp.tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="text-xs font-semibold tracking-widest uppercase border border-current px-2 py-0.5">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <h2 className={`text-xl md:text-2xl font-medium mt-1 leading-snug ${soldOut ? "text-gray-400" : ""}`}>
                    {exp.name}
                  </h2>
                  {exp.shortDescription && (
                    <p className={`text-sm mt-1 truncate ${soldOut ? "text-gray-300" : "text-gray-500 group-hover:text-gray-300"}`}>
                      {exp.shortDescription}
                    </p>
                  )}
                  {exp.location && (
                    <p className={`flex items-center gap-1 mt-2 text-sm ${soldOut ? "text-gray-300" : "text-gray-500 group-hover:text-gray-300"}`}>
                      <MapPin size={12} />
                      {exp.location}
                    </p>
                  )}
                </div>

                {/* Price + spots */}
                <div className="hidden md:block text-right">
                  {price > 0 ? (
                    <p className={`text-xl font-bold ${soldOut ? "text-gray-300" : ""}`}>{price} {exp.currency}</p>
                  ) : (
                    <p className={`text-sm font-semibold tracking-widest uppercase ${soldOut ? "text-gray-300" : ""}`}>Free</p>
                  )}
                  {maxSpots > 0 && (
                    <p className={`text-xs mt-1 ${
                      soldOut ? "text-red-400"
                      : spotsLeft <= 5 ? "text-amber-500 group-hover:text-amber-300"
                      : "text-gray-400 group-hover:text-gray-300"
                    }`}>
                      {soldOut ? "Sold out" : `${spotsLeft} spots left`}
                    </p>
                  )}
                </div>

                {soldOut
                  ? <span className="text-xs font-semibold tracking-widest uppercase text-gray-300">Sold out</span>
                  : <ArrowRight size={16} className="flex-shrink-0" />
                }
              </>
            );

            return soldOut ? (
              <div
                key={session.id}
                className="grid grid-cols-[80px_1fr_auto] md:grid-cols-[100px_1fr_200px_auto] items-center gap-6 py-8 px-2 -mx-2 opacity-50"
              >
                {sharedContent}
              </div>
            ) : (
              <Link
                key={session.id}
                href={`/with-us/${session.id}`}
                className="group grid grid-cols-[80px_1fr_auto] md:grid-cols-[100px_1fr_200px_auto] items-center gap-6 py-8 hover:bg-black hover:text-white transition-colors px-2 -mx-2"
              >
                {sharedContent}
              </Link>
            );
          })}
        </div>
      )}

      <PrivateExperienceSection experiences={privateExperiences} />
    </div>
  );
}
