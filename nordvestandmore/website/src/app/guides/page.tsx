import { getGuides } from "@/lib/notion";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Guides | NV & more",
  description:
    "Curated guides to Nordvest, Copenhagen — cafés, bars, bakeries, wellness, community life and more.",
};

export const revalidate = 3600;

export default async function GuidesHubPage() {
  const guides = await getGuides();

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      <div className="border-b border-black pb-8 mb-12">
        <p className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-2">NV & more</p>
        <h1
          className="text-5xl md:text-7xl font-thin leading-tight tracking-tight -ml-1"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          Guides
        </h1>
        <p className="mt-4 text-gray-600 max-w-2xl">
          Hand-picked collections — places, articles and stories from around Nordvest.
        </p>
      </div>

      {guides.length === 0 ? (
        <p className="text-gray-500">No guides published yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {guides.map((g) => {
            const fallbackImg = g.posts[0]?.coverImage;
            const img = g.heroImage || fallbackImg;
            const itemCount = g.locations.length + g.posts.length;
            return (
              <Link
                key={g.id}
                href={`/guides/${g.slug}`}
                className="group block border border-black hover:bg-black hover:text-white transition-colors"
              >
                {img && (
                  <div className="relative aspect-[4/3] overflow-hidden border-b border-black">
                    <Image
                      src={img}
                      alt={g.title}
                      fill
                      sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
                      className="object-cover"
                    />
                  </div>
                )}
                <div className="p-6">
                  <h2
                    className="text-2xl mb-2 leading-tight"
                    style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
                  >
                    {g.title}
                  </h2>
                  {g.description && (
                    <p className="text-sm leading-relaxed mb-3 opacity-80">{g.description}</p>
                  )}
                  <p className="text-xs tracking-[0.2em] uppercase opacity-60">
                    {itemCount} {itemCount === 1 ? "entry" : "entries"}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
