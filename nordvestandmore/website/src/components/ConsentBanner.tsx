"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const STORAGE_KEY = "cookie_consent";

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export default function ConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setVisible(true);
    } else if (stored === "granted" && window.gtag) {
      window.gtag("consent", "update", { analytics_storage: "granted" });
    }
  }, []);

  function accept() {
    localStorage.setItem(STORAGE_KEY, "granted");
    if (window.gtag) {
      window.gtag("consent", "update", { analytics_storage: "granted" });
    }
    setVisible(false);
  }

  function decline() {
    localStorage.setItem(STORAGE_KEY, "denied");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-black">
      <div className="max-w-6xl mx-auto px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <p className="text-sm leading-relaxed max-w-2xl">
          We use cookies for analytics to understand how visitors use the site.
          No tracking happens until you accept.{" "}
          <Link href="/privacy" className="underline">
            Privacy policy
          </Link>
          .
        </p>
        <div className="flex gap-3 shrink-0">
          <button
            onClick={decline}
            className="text-xs tracking-widest uppercase border border-black px-4 py-2 hover:bg-black hover:text-white transition"
          >
            Decline
          </button>
          <button
            onClick={accept}
            className="text-xs tracking-widest uppercase border border-black bg-black text-white px-4 py-2 hover:bg-white hover:text-black transition"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
