"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import dynamic from "next/dynamic";

const SearchModal = dynamic(() => import("@/components/SearchModal"), { ssr: false });

const links = [
  { href: "/events", label: "Events" },
  { href: "/guide", label: "Guide" },
  { href: "/blog", label: "Blog" },
  { href: "/with-us", label: "Our events" },
  { href: "/about", label: "About" },
];

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  const closeSearch = useCallback(() => setSearchOpen(false), []);

  // ⌘K / Ctrl+K shortcut
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <header className="border-b border-black sticky top-0 bg-white z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/">
            <Image
              src="/logo.jpg"
              alt="NV & more"
              width={44}
              height={44}
              className="rounded-full"
              priority
            />
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`text-sm font-medium tracking-widest uppercase transition-opacity hover:opacity-50 ${
                  pathname.startsWith(l.href) ? "border-b border-black" : ""
                }`}
              >
                {l.label}
              </Link>
            ))}
            <button
              onClick={() => setSearchOpen(true)}
              className="hover:opacity-50 transition-opacity"
              aria-label="Search"
            >
              <Search size={16} />
            </button>
          </nav>

          {/* Mobile right side */}
          <div className="md:hidden flex items-center gap-4">
            <button
              onClick={() => setSearchOpen(true)}
              className="hover:opacity-50 transition-opacity"
              aria-label="Search"
            >
              <Search size={16} />
            </button>
            <button
              className="flex flex-col gap-1.5 p-1"
              onClick={() => setOpen(!open)}
              aria-label="Toggle menu"
            >
              <span className={`block w-6 h-px bg-black transition-transform ${open ? "rotate-45 translate-y-2" : ""}`} />
              <span className={`block w-6 h-px bg-black transition-opacity ${open ? "opacity-0" : ""}`} />
              <span className={`block w-6 h-px bg-black transition-transform ${open ? "-rotate-45 -translate-y-2" : ""}`} />
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {open && (
          <div className="md:hidden border-t border-black bg-white">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block px-6 py-4 text-sm font-medium tracking-widest uppercase border-b border-black hover:bg-black hover:text-white transition-colors"
              >
                {l.label}
              </Link>
            ))}
          </div>
        )}
      </header>

      {searchOpen && <SearchModal onClose={closeSearch} />}
    </>
  );
}
