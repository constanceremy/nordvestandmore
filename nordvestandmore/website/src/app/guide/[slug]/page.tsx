import { getLocations, getLocationBySlug, getEventsByLocation, getBlogPostsByLocation } from "@/lib/notion";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, MapPin } from "lucide-react";
import LocationMapWrapper from "@/components/LocationMapWrapper";
import type { Metadata } from "next";

export const revalidate = 3600;
export const dynamicParams = true;

export async function generateStaticParams() {
  const locations = await getLocations();
  return locations.map((l) => ({ slug: l.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const location = await getLocationBySlug(slug);
  if (!location) return {};
  return {
    title: `${location.name} | NV & more Guide`,
    description: `${location.name} — ${location.tags.join(", ")} in Nordvest, Copenhagen`,
  };
}

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", { day: "numeric", month: "short" }).toUpperCase();
}

function formatTime(iso: string) {
  if (!iso || !iso.includes("T")) return "";
  return new Date(iso).toLocaleTimeString("en-DK", { hour: "2-digit", minute: "2-digit" });
}

export default async function LocationPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [location, allLocations] = await Promise.all([
    getLocationBySlug(slug),
    getLocations(),
  ]);
  if (!location) notFound();

  const [events, posts] = await Promise.all([
    getEventsByLocation(location.id),
    getBlogPostsByLocation(location.id),
  ]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Back */}
      <Link
        href="/guide"
        className="inline-flex items-center gap-2 text-xs tracking-[0.2em] uppercase hover:opacity-50 transition-opacity mb-12"
      >
        <ArrowLeft size={12} />
        The Guide
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
        {/* Left: map */}
        <div>
          {location.lat && location.lng ? (
            <div className="w-full aspect-[4/3] border border-black mb-8">
              <LocationMapWrapper locations={allLocations} activeSlug={slug} />
            </div>
          ) : (
            <div className="w-full aspect-[4/3] bg-gray-100 mb-8 flex items-center justify-center border border-black">
              <MapPin size={24} className="text-gray-300" />
            </div>
          )}

          {/* Tags */}
          {location.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {location.tags.map((tag) => (
                <Link
                  key={tag}
                  href={`/guide?tag=${tag}`}
                  className="text-xs tracking-[0.15em] uppercase border border-black px-3 py-1 hover:bg-black hover:text-white transition-colors"
                >
                  {tag}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Right: info + related */}
        <div>
          <h1
            className="text-4xl md:text-5xl font-thin mb-8 leading-tight"
            style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
          >
            {location.name}
          </h1>

          {/* Upcoming events */}
          {events.length > 0 && (
            <div className="mb-10">
              <p className="text-xs tracking-[0.3em] uppercase border-b border-black pb-3 mb-3">
                Upcoming events here
              </p>
              <div className="divide-y divide-black">
                {events.map((event) => (
                  <div key={event.id} className="group relative flex items-center justify-between gap-4 py-3 hover:bg-black hover:text-white transition-colors px-2 -mx-2">
                    {event.ownEvent ? (
                      <Link href={`/events/${event.slug}`} className="absolute inset-0" aria-label={event.title} />
                    ) : (
                      <a href={event.notionUrl || "#"} target="_blank" rel="noopener noreferrer" className="absolute inset-0" aria-label={event.title} />
                    )}
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="text-center flex-shrink-0 w-10">
                        <p className="text-xs text-gray-400 group-hover:text-gray-300 leading-none">{formatDate(event.date)}</p>
                        {formatTime(event.date) && <p className="text-xs text-gray-400 group-hover:text-gray-300 mt-0.5">{formatTime(event.date)}</p>}
                      </div>
                      <p className="text-sm font-medium truncate">{event.title}</p>
                    </div>
                    <ArrowRight size={12} className="flex-shrink-0 pointer-events-none" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related articles */}
          {posts.length > 0 && (
            <div>
              <p className="text-xs tracking-[0.3em] uppercase border-b border-black pb-3 mb-3">
                From the blog
              </p>
              <div className="divide-y divide-black">
                {posts.map((post) => (
                  <Link
                    key={post.id}
                    href={`/blog/${post.slug}`}
                    className="group flex items-center justify-between gap-4 py-3 hover:bg-black hover:text-white transition-colors px-2 -mx-2"
                  >
                    <p className="text-sm font-medium leading-snug">{post.title}</p>
                    <ArrowRight size={12} className="flex-shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
          )}

          {events.length === 0 && posts.length === 0 && (
            <p className="text-xs tracking-[0.2em] uppercase text-gray-400">
              No events or articles linked yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
