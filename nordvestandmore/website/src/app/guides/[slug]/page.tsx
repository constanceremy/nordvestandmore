import { getGuides, getGuideBySlug } from "@/lib/notion";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, MapPin } from "lucide-react";
import type { Metadata } from "next";

export const revalidate = 3600;
export const dynamicParams = true;

export async function generateStaticParams() {
  const guides = await getGuides();
  return guides.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const guide = await getGuideBySlug(slug);
  if (!guide) return {};
  return {
    title: `${guide.title} | NV & more`,
    description: guide.description || `A curated guide to ${guide.title.toLowerCase()} in Nordvest.`,
    openGraph: {
      title: guide.title,
      description: guide.description || undefined,
      images: guide.heroImage ? [{ url: guide.heroImage }] : [],
    },
  };
}

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default async function GuidePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = await getGuideBySlug(slug);
  if (!guide) notFound();

  const hasLocations = guide.locations.length > 0;
  const hasPosts = guide.posts.length > 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-16">
      {/* Back link */}
      <Link
        href="/guides"
        className="inline-flex items-center gap-2 text-xs tracking-[0.2em] uppercase mb-8 hover:opacity-50 transition-opacity"
      >
        <ArrowLeft size={12} />
        All guides
      </Link>

      {/* Hero */}
      <div className="border-b border-black pb-10 mb-12">
        <p className="text-xs tracking-[0.3em] uppercase text-gray-400 mb-2">Guide</p>
        <h1
          className="text-5xl md:text-7xl font-thin leading-tight tracking-tight -ml-1"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          {guide.title}
        </h1>
        {guide.description && (
          <p className="mt-6 text-lg text-gray-700 max-w-2xl">{guide.description}</p>
        )}
      </div>

      {/* Hero image */}
      {guide.heroImage && (
        <div className="relative aspect-[16/9] overflow-hidden border border-black mb-12">
          <Image
            src={guide.heroImage}
            alt={guide.title}
            fill
            sizes="(max-width: 1024px) 100vw, 1024px"
            className="object-cover"
            priority
          />
        </div>
      )}

      {/* Intro */}
      {guide.intro && (
        <div className="prose prose-lg max-w-none mb-16 text-gray-700 leading-relaxed whitespace-pre-line">
          {guide.intro}
        </div>
      )}

      {/* Places */}
      {hasLocations && (
        <section className="mb-16">
          <h2
            className="text-xs font-semibold tracking-[0.3em] uppercase text-gray-400 mb-6 border-b border-black pb-3"
          >
            Places ({guide.locations.length})
          </h2>
          <ul className="divide-y divide-black border-b border-black">
            {guide.locations.map((loc) => (
              <li key={loc.id} className="py-6 flex flex-col md:flex-row md:items-baseline md:justify-between gap-2">
                <div>
                  <Link
                    href={`/map/${loc.slug}`}
                    className="text-xl hover:underline underline-offset-4"
                    style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
                  >
                    {loc.name}
                  </Link>
                  {loc.tags.length > 0 && (
                    <p className="mt-1 text-xs tracking-[0.15em] uppercase text-gray-500">
                      {loc.tags.slice(0, 4).join(" · ")}
                    </p>
                  )}
                </div>
                <Link
                  href={`/map/${loc.slug}`}
                  className="text-xs tracking-[0.2em] uppercase inline-flex items-center gap-1 hover:opacity-50 transition-opacity shrink-0"
                >
                  <MapPin size={12} /> View
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Articles */}
      {hasPosts && (
        <section className="mb-16">
          <h2
            className="text-xs font-semibold tracking-[0.3em] uppercase text-gray-400 mb-6 border-b border-black pb-3"
          >
            Read on ({guide.posts.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {guide.posts.map((post) => (
              <Link
                key={post.id}
                href={`/blog/${post.slug}`}
                className="group block"
              >
                {post.coverImage && (
                  <div className="relative aspect-[4/3] overflow-hidden border border-black mb-4">
                    <Image
                      src={post.coverImage}
                      alt={post.title}
                      fill
                      sizes="(max-width: 768px) 100vw, 50vw"
                      className="object-cover group-hover:scale-[1.02] transition-transform duration-500"
                    />
                  </div>
                )}
                <p className="text-xs tracking-[0.2em] uppercase text-gray-400 mb-1">
                  {formatDate(post.publishedDate)}
                </p>
                <h3
                  className="text-xl leading-tight group-hover:underline underline-offset-4"
                  style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
                >
                  {post.title}
                </h3>
                {post.excerpt && (
                  <p className="mt-2 text-sm text-gray-600 leading-relaxed line-clamp-2">
                    {post.excerpt}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {!hasLocations && !hasPosts && (
        <p className="text-gray-500">This guide is being prepared — no entries yet.</p>
      )}

      {/* Footer nav */}
      <div className="border-t border-black pt-10 mt-16">
        <Link
          href="/guides"
          className="text-sm tracking-[0.2em] uppercase underline underline-offset-4 hover:opacity-50 transition-opacity"
        >
          ← All guides
        </Link>
      </div>
    </div>
  );
}
