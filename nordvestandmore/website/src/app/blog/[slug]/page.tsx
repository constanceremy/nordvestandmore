import { getBlogPostBySlug, getBlogPosts, getPageBlocks, getLocations } from "@/lib/notion";
import { notFound } from "next/navigation";
import NotionBlocks from "@/components/NotionBlocks";
import Link from "next/link";
import { ArrowLeft, MapPin } from "lucide-react";
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) return {};
  return {
    title: `${post.title} | NV & more`,
    description: post.excerpt || undefined,
    openGraph: {
      title: post.title,
      description: post.excerpt || undefined,
      images: post.coverImage ? [{ url: post.coverImage }] : [],
      type: "article",
    },
  };
}

export const revalidate = 3600;

export async function generateStaticParams() {
  return [];
}

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) notFound();

  const [blocks, allLocations] = await Promise.all([
    getPageBlocks(post.id),
    post.locationIds.length > 0 ? getLocations() : Promise.resolve([]),
  ]);
  const postLocations = allLocations.filter((l) => post.locationIds.includes(l.id));

  return (
    <article className="max-w-3xl mx-auto px-6 py-16">
      {/* Back */}
      <Link
        href="/blog"
        className="inline-flex items-center gap-2 text-sm font-medium tracking-widest uppercase hover:opacity-50 transition-opacity mb-12"
      >
        <ArrowLeft size={14} />
        Blog
      </Link>

      {/* Header */}
      <header className="mb-10">
        <div className="flex flex-wrap items-center gap-4 mb-4 text-xs font-semibold tracking-widest uppercase text-gray-400">
          <span>{formatDate(post.publishedDate)}</span>
          {post.tags.map((tag) => (
            <Link key={tag} href={`/blog?tag=${encodeURIComponent(tag)}`} className="hover:underline underline-offset-4">
              {tag}
            </Link>
          ))}
          <span>By {post.author}</span>
        </div>

        <h1
          className="text-4xl md:text-6xl leading-tight mb-6"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          {post.title}
        </h1>

        {post.excerpt && (
          <p className="text-xl text-gray-500 leading-relaxed border-l-2 border-black pl-4">
            {post.excerpt}
          </p>
        )}
      </header>

      {/* Body */}
      <div className="prose prose-lg max-w-none">
        <NotionBlocks blocks={blocks} />
      </div>

      {/* Places in this article */}
      {postLocations.length > 0 && (
        <div className="mt-12 pt-8 border-t border-black">
          <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-4">
            Places in this article
          </p>
          <div className="flex flex-wrap gap-2">
            {postLocations.map((loc) => (
              <Link
                key={loc.id}
                href={`/guide/${loc.slug}`}
                className="inline-flex items-center gap-1.5 border border-black px-3 py-1.5 text-xs font-semibold tracking-widest uppercase hover:bg-black hover:text-white transition-colors"
              >
                <MapPin size={10} />
                {loc.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}
