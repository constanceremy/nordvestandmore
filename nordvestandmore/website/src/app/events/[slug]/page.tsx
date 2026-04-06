import { getEventBySlug, getEvents } from "@/lib/notion";
import { notFound } from "next/navigation";
import BookButton from "@/components/BookButton";
import AddToCalendar from "@/components/AddToCalendar";
import { Calendar, MapPin, Users, RefreshCw, User, Instagram } from "lucide-react";
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event) return {};
  return {
    title: `${event.title} | NV & more`,
    description: event.description || `${event.title} — ${event.location || "Nordvest, Copenhagen"}`,
    openGraph: {
      title: event.title,
      description: event.description || undefined,
      images: event.coverImage ? [{ url: event.coverImage }] : [],
    },
  };
}

export const revalidate = 3600;

export const dynamicParams = true;

export async function generateStaticParams() {
  const events = await getEvents(false);
  return events.filter((e) => e.ownEvent).map((e) => ({ slug: e.slug }));
}

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatTime(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-DK", { hour: "2-digit", minute: "2-digit" });
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event) notFound();

  const spotsLeft = event.maxSpots - event.bookedSpots;
  const soldOut = event.maxSpots > 0 && spotsLeft <= 0;

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
        {/* Left: Image + meta */}
        <div>
          {event.coverImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={event.coverImage}
              alt={event.title}
              className="w-full aspect-[4/3] object-cover grayscale mb-8"
            />
          ) : (
            <div className="w-full aspect-[4/3] bg-gray-100 mb-8 flex items-center justify-center border border-black">
              <span className="text-6xl text-gray-300" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>NV</span>
            </div>
          )}

          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-px bg-black border border-black">
            <div className="bg-white p-4">
              <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Date</p>
              <p className="text-sm font-medium flex items-center gap-1">
                <Calendar size={12} />
                {formatDate(event.date)}
              </p>
            </div>
            <div className="bg-white p-4">
              <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Time</p>
              <p className="text-sm font-medium">
                {formatTime(event.date)}
                {event.endDate && ` – ${formatTime(event.endDate)}`}
              </p>
            </div>
            {event.location && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Location</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <MapPin size={12} />
                  {event.location}
                </p>
              </div>
            )}
            {event.organizer && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Organizer</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <User size={12} />
                  {event.organizer}
                </p>
              </div>
            )}
            {event.instagramHandle && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Instagram</p>
                <a
                  href={`https://instagram.com/${event.instagramHandle.replace("@", "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium flex items-center gap-1 hover:underline"
                >
                  <Instagram size={12} />
                  {event.instagramHandle}
                </a>
              </div>
            )}
            {event.maxSpots > 0 && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Availability</p>
                <p className={`text-sm font-medium flex items-center gap-1 ${soldOut ? "text-red-600" : spotsLeft <= 5 ? "text-amber-600" : ""}`}>
                  <Users size={12} />
                  {soldOut ? "Sold out" : `${spotsLeft} of ${event.maxSpots} spots left`}
                </p>
              </div>
            )}
            {event.isRecurring && (
              <div className="bg-white p-4 col-span-2">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Recurring</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <RefreshCw size={12} />
                  {event.recurrenceRule || "Recurring event"}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Content + booking */}
        <div>
          {event.eventType && (
            <span className="text-xs font-semibold tracking-widest uppercase border border-black px-3 py-1 mb-4 inline-block">
              {event.eventType}
            </span>
          )}

          <h1
            className="text-4xl md:text-5xl mt-3 mb-6 leading-tight"
            style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
          >
            {event.title}
          </h1>

          {event.description && (
            <div className="prose prose-sm max-w-none text-gray-700 mb-8 leading-relaxed">
              {event.description.split("\n").map((para, i) => (
                <p key={i} className="mb-3">{para}</p>
              ))}
            </div>
          )}

          {/* Tags */}
          {event.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-8">
              {event.tags.map((tag) => (
                <span key={tag} className="text-xs font-semibold tracking-widest uppercase text-gray-500 border border-gray-300 px-2 py-1">
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Booking CTA */}
          <div className="border border-black p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-3xl font-bold">
                  {event.price === 0 ? "Free" : `${event.price} ${event.currency}`}
                </p>
                {event.maxSpots > 0 && !soldOut && (
                  <p className="text-sm text-gray-500 mt-0.5">{spotsLeft} spots remaining</p>
                )}
              </div>
              {soldOut && (
                <span className="text-sm font-semibold tracking-widest uppercase text-red-600 border border-red-600 px-3 py-1">
                  Sold out
                </span>
              )}
            </div>

            <BookButton
              eventId={event.id}
              eventSlug={event.slug}
              eventTitle={event.title}
              price={event.price}
              currency={event.currency}
              stripeProductId={event.stripeProductId}
              soldOut={soldOut}
            />

            <p className="text-xs text-gray-400 mt-3 text-center">
              Secure payment via Stripe. You'll receive a confirmation email.
            </p>
          </div>

          <div className="mt-4">
            <AddToCalendar
              title={event.title}
              date={event.date}
              location={event.location}
              description={event.description}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
