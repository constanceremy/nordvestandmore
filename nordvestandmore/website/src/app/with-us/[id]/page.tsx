import { getSessionById, getSessions } from "@/lib/notion";
import { notFound } from "next/navigation";
import BookButton from "@/components/BookButton";
import AddToCalendar from "@/components/AddToCalendar";
import Link from "next/link";
import { ArrowLeft, Calendar, MapPin, Users, Clock, Globe } from "lucide-react";
import type { Metadata } from "next";

export const revalidate = 3600;

export async function generateStaticParams() {
  const sessions = await getSessions(false);
  return sessions.map((s) => ({ id: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const session = await getSessionById(id);
  if (!session?.experience) return {};
  const exp = session.experience;
  return {
    title: `${exp.name} | NV & more`,
    description: exp.shortDescription || exp.description || undefined,
    openGraph: {
      title: exp.name,
      description: exp.shortDescription || exp.description || undefined,
      images: exp.coverImage ? [{ url: exp.coverImage }] : [],
    },
  };
}

function formatDate(dateStr: string) {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("en-DK", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await getSessionById(id);
  if (!session?.experience) notFound();

  const exp = session.experience;
  const policy = session.bookingPolicy;
  const price = session.priceOverride ?? exp.price;
  const maxSpots = session.maxSpots || exp.maxSpots;
  const spotsLeft = maxSpots - session.bookedSpots;
  const soldOut = maxSpots > 0 && spotsLeft <= 0;

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Back */}
      <Link
        href="/with-us"
        className="inline-flex items-center gap-2 text-sm font-medium tracking-widest uppercase hover:opacity-50 transition-opacity mb-12"
      >
        <ArrowLeft size={14} />
        With us
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
        {/* Left: image + meta */}
        <div>
          {exp.coverImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={exp.coverImage}
              alt={exp.name}
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
                {formatDate(session.date)}
              </p>
            </div>
            <div className="bg-white p-4">
              <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Time</p>
              <p className="text-sm font-medium flex items-center gap-1">
                <Clock size={12} />
                {session.startTime}
                {session.endTime && ` – ${session.endTime}`}
              </p>
            </div>
            {exp.meetingPoint && (
              <div className="bg-white p-4 col-span-2">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Meeting point</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <MapPin size={12} />
                  {exp.meetingPoint}
                </p>
              </div>
            )}
            {exp.duration && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Duration</p>
                <p className="text-sm font-medium">{exp.duration}</p>
              </div>
            )}
            {maxSpots > 0 && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Availability</p>
                <p className={`text-sm font-medium flex items-center gap-1 ${soldOut ? "text-red-600" : spotsLeft <= 5 ? "text-amber-600" : ""}`}>
                  <Users size={12} />
                  {soldOut ? "Sold out" : `${spotsLeft} of ${maxSpots} spots left`}
                </p>
              </div>
            )}
            {exp.language.length > 0 && (
              <div className="bg-white p-4">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-1">Language</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <Globe size={12} />
                  {exp.language.join(", ")}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right: content + booking */}
        <div>
          {exp.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {exp.tags.map((tag) => (
                <span key={tag} className="text-xs font-semibold tracking-widest uppercase border border-black px-3 py-1">
                  {tag}
                </span>
              ))}
            </div>
          )}

          <h1
            className="text-4xl md:text-5xl mt-2 mb-6 leading-tight"
            style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
          >
            {exp.name}
          </h1>

          {exp.description && (
            <div className="text-gray-700 mb-8 leading-relaxed space-y-3">
              {exp.description.split("\n").filter(Boolean).map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          )}

          {/* What's included / what to bring */}
          {(exp.whatsIncluded || exp.whatToBring) && (
            <div className="grid grid-cols-1 gap-px bg-black border border-black mb-8">
              {exp.whatsIncluded && (
                <div className="bg-white p-4">
                  <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-2">What's included</p>
                  <p className="text-sm text-gray-700 leading-relaxed">{exp.whatsIncluded}</p>
                </div>
              )}
              {exp.whatToBring && (
                <div className="bg-white p-4">
                  <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-2">What to bring</p>
                  <p className="text-sm text-gray-700 leading-relaxed">{exp.whatToBring}</p>
                </div>
              )}
            </div>
          )}

          {/* Booking box */}
          <div className="border border-black p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-3xl font-bold">
                  {price === 0 ? "Free" : `${price} ${exp.currency}`}
                </p>
                {maxSpots > 0 && !soldOut && (
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
              eventId={session.id}
              eventSlug={session.id}
              eventTitle={exp.name}
              eventDate={session.date}
              price={price}
              currency={exp.currency}
              stripeProductId={exp.stripeProductId}
              soldOut={soldOut}
            />

            <p className="text-xs text-gray-400 mt-3 text-center">
              Secure payment via Stripe. You'll receive a confirmation email.
            </p>
          </div>

          <div className="mt-4">
            <AddToCalendar
              title={exp.name}
              date={session.date}
              startTime={session.startTime}
              endTime={session.endTime}
              location={exp.meetingPoint}
              description={exp.shortDescription || exp.description}
            />
          </div>

          {/* Booking policy */}
          {policy?.fullPolicyText && (
            <div className="mt-6 border-t border-gray-200 pt-6">
              <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">Booking policy</p>
              <div className="text-sm text-gray-600 leading-relaxed space-y-2">
                {policy.fullPolicyText.split("\n").filter(Boolean).map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-400 mt-6">
            By booking you agree to our{" "}
            <Link href="/terms" className="underline underline-offset-2 hover:opacity-50">
              Terms of Sale
            </Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
