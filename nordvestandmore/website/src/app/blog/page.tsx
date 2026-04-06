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

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Nordvest stories
        </p>
        <h1
          className="text-5xl md:text-7xl"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          Blog
        </h1>
        {tag && (
          <div className="flex items-center gap-4 mt-6">
            <span className="text-xs font-semibold tracking-widest uppercase bg-black text-white px-3 py-1">
              {tag}
            </span>
            <Link
              href="/blog"
              className="text-xs tracking-widest uppercase underline underline-offset-4 hover:opacity-50 transition-opacity"
            >
              Clear
            </Link>
          </div>
        )}
      </div>

      {posts.length === 0 ? (
        <p className="text-gray-400">No posts found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-black border border-black">
          {posts.map((post, i) => (
            <Link
              key={post.id}
              href={`/blog/${post.slug}`}
              className={`group bg-white p-8 hover:bg-black hover:text-white transition-colors flex flex-col ${
                i === 0 && !tag ? "md:col-span-2" : ""
              }`}
            >
              <div className="flex items-center gap-4 mb-3">
                <p className="text-xs text-gray-400 group-hover:text-gray-300">
                  {formatDate(post.publishedDate)}
                </p>
                {post.tags.slice(0, 2).map((t) => (
                  <span
                    key={t}
                    onClick={(e) => {
                      e.preventDefault();
                      window.location.href = `/blog?tag=${encodeURIComponent(t)}`;
                    }}
                    className="text-xs font-semibold tracking-widest uppercase text-gray-400 group-hover:text-gray-300 hover:underline underline-offset-4 cursor-pointer"
                  >
                    {t}
                  </span>
                ))}
              </div>
              <h2
                className={`font-medium leading-snug mb-2 ${i === 0 && !tag ? "text-3xl md:text-4xl" : "text-xl"}`}
                style={i === 0 && !tag ? { fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" } : {}}
              >
                {post.title}
              </h2>
              {post.excerpt && (
                <p className="text-sm text-gray-500 group-hover:text-gray-300 line-clamp-3 flex-1 leading-relaxed">
                  {post.excerpt}
                </p>
              )}
              <p className="text-xs font-semibold tracking-widest uppercase mt-4 underline underline-offset-4 group-hover:text-white">
                Read more
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
