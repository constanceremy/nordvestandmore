"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}

function Inner({ gaId }: { gaId: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!window.gtag) return;
    const qs = searchParams.toString();
    const url = qs ? `${pathname}?${qs}` : pathname;
    window.gtag("event", "page_view", { page_path: url });
  }, [pathname, searchParams, gaId]);

  return null;
}

export default function GAPageView({ gaId }: { gaId: string }) {
  return (
    <Suspense fallback={null}>
      <Inner gaId={gaId} />
    </Suspense>
  );
}
