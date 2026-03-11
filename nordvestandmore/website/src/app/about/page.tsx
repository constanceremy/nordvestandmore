import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Who we are
        </p>
        <h1
          className="text-5xl md:text-7xl"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          About
        </h1>
      </div>

      <div className="prose prose-lg max-w-none space-y-6 text-gray-700 leading-relaxed">
        <p>
          <strong>NV & more</strong> is a guide to Nordvest — one of Copenhagen's most vibrant and
          diverse neighbourhoods. We cover what's on, where to go, and the stories behind the places
          and people that make this neighbourhood special.
        </p>
        <p>
          From local events and workshops to hidden gems and neighbourhood guides — this is your go-to
          resource for everything Nordvest.
        </p>
      </div>

      <div className="mt-16 border-t border-black pt-10">
        <h2
          className="text-2xl mb-6"
          style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
        >
          Get in touch
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Have an event you'd like featured? A story to share? Get in touch.
        </p>
        <a
          href="mailto:nordvestandmore@gmail.com"
          className="inline-block bg-black text-white px-6 py-3 text-sm font-semibold tracking-widest uppercase hover:bg-gray-900 transition-colors"
        >
          nordvestandmore@gmail.com
        </a>
      </div>

      <div className="mt-10">
        <Link
          href="/events"
          className="text-sm font-medium tracking-widest uppercase underline underline-offset-4 hover:opacity-50 transition-opacity"
        >
          Browse upcoming events →
        </Link>
      </div>
    </div>
  );
}
