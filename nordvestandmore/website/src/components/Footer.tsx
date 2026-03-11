import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-black mt-24">
      <div className="max-w-6xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-3 gap-10">
        {/* Brand */}
        <div>
          <p className="font-serif text-2xl mb-2">NV & more</p>
          <p className="text-sm text-gray-500 leading-relaxed">
            Events, guides and stories from Nordvest — Copenhagen's most vibrant neighbourhood.
          </p>
        </div>

        {/* Links */}
        <div>
          <p className="text-xs font-semibold tracking-widest uppercase mb-4">Explore</p>
          <ul className="space-y-2">
            {[
              { href: "/events", label: "Events" },
              { href: "/with-us", label: "With us" },
              { href: "/blog", label: "Blog" },
              { href: "/about", label: "About" },
              { href: "/terms", label: "Terms of Sale" },
              { href: "/privacy", label: "Privacy Policy" },
            ].map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-sm hover:underline">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {/* Social */}
        <div>
          <p className="text-xs font-semibold tracking-widest uppercase mb-4">Follow</p>
          <ul className="space-y-2">
            <li>
              <a
                href="https://instagram.com/nordvestandmore"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm hover:underline"
              >
                Instagram
              </a>
            </li>
            <li>
              <a
                href="https://www.facebook.com/profile.php?id=61573178770564"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm hover:underline"
              >
                Facebook
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-black">
        <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
          <p className="text-xs text-gray-400">© {new Date().getFullYear()} NV & more</p>
          <p className="text-xs text-gray-400">Nordvest, Copenhagen</p>
        </div>
      </div>
    </footer>
  );
}
