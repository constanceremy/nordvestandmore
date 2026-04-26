import { getBlogPosts } from "@/lib/notion";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Blog | NV & more",
  description: "Stories, guides and local favourites from Nordvest, Copenhagen.",
  openGraph: {
    title: "Blog | NV & more",
    description: "Stories, guides and local favourites from Nordvest, Copenhagen.",
  },
};

export const revalidate = 3600;

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-DK", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function BlogPage({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>;
}) {
  const { tag } = await searchParams;
  const allPosts = await getBlogPosts();
  const posts = tag ? allPosts.filter((p) => p.tags.includes(tag)) : allPosts;

  const allTags = [...new Set(allPosts.flatMap((p) => p.tags))].sort();

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-8 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Nordvest stories
        </p>
        <h1
          className="text-5xl md:text-7xl"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          Blog
        </h1>
      </div>

      {/* Tag filters */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-10">
          <Link
            href="/blog"
            className={`text-xs font-semibold tracking-widest uppercase px-3 py-1.5 border transition-colors ${
              !tag ? "bg-black text-white border-black" : "border-black hover:bg-black hover:text-white"
            }`}
          >
            All
          </Link>
          {allTags.map((t) => (
            <Link
              key={t}
              href={`/blog?tag=${encodeURIComponent(t)}`}
              className={`text-xs font-semibold tracking-widest uppercase px-3 py-1.5 border transition-colors ${
                tag === t ? "bg-black text-white border-black" : "border-black hover:bg-black hover:text-white"
              }`}
            >
              {t}
            </Link>
          ))}
        </div>
      )}

      {posts.length === 0 ? (
        <p className="text-gray-400">No posts found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-black border border-black">
          {posts.map((post, i) => (
            <div
              key={post.id}
              className={`bg-white p-8 flex flex-col ${i === 0 && !tag ? "md:col-span-2" : ""}`}
            >
              <div className="flex items-center gap-4 mb-3">
                <p className="text-xs text-gray-400">
                  {formatDate(post.publishedDate)}
                </p>
                {post.tags.slice(0, 2).map((t) => (
                  <Link
                    key={t}
                    href={`/blog?tag=${encodeURIComponent(t)}`}
                    className="text-xs font-semibold tracking-widest uppercase text-gray-400 hover:text-black underline underline-offset-4"
                  >
                    {t}
                  </Link>
                ))}
              </div>
              <Link href={`/blog/${post.slug}`} className="group flex flex-col flex-1 hover:opacity-60 transition-opacity">
                <h2
                  className={`font-medium leading-snug mb-2 ${i === 0 && !tag ? "text-3xl md:text-4xl" : "text-xl"}`}
                  style={i === 0 && !tag ? { fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" } : {}}
                >
                  {post.title}
                </h2>
                {post.excerpt && (
                  <p className="text-sm text-gray-500 line-clamp-3 flex-1 leading-relaxed">
                    {post.excerpt}
                  </p>
                )}
                <p className="text-xs font-semibold tracking-widest uppercase mt-4 underline underline-offset-4">
                  Read more
                </p>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
