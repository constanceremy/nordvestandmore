import { getLocations, getEventsByLocation, getBlogPostsByLocation } from "@/lib/notion";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, MapPin } from "lucide-react";
import LocationMapWrapper from "@/components/LocationMapWrapper";
import LocationTabs from "@/components/LocationEvents";
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
  const locations = await getLocations();
  const location = locations.find((l) => l.slug === slug);
  if (!location) return {};
  return {
    title: `${location.name} | NV & more`,
    description: `${location.name} — ${location.tags.join(", ")} in Nordvest, Copenhagen`,
  };
}


export default async function LocationPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const allLocations = await getLocations();
  const location = allLocations.find((l) => l.slug === slug) ?? null;
  if (!location) notFound();

  const [events, posts] = await Promise.all([
    getEventsByLocation(location.id),
    getBlogPostsByLocation(location.id),
  ]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Back */}
      <Link
        href="/map"
        className="inline-flex items-center gap-2 text-xs tracking-[0.2em] uppercase hover:opacity-50 transition-opacity mb-12"
      >
        <ArrowLeft size={12} />
        The Map
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
                  href={`/map?tag=${tag}`}
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

          <LocationTabs events={events} posts={posts} />
        </div>
      </div>
    </div>
  );
}
