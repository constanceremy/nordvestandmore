"use client";

import dynamic from "next/dynamic";
import type { LocationItem } from "@/lib/notion";

const GuideMap = dynamic(() => import("@/components/GuideMap"), { ssr: false });

export default function LocationMapWrapper({
  locations,
  activeSlug,
}: {
  locations: LocationItem[];
  activeSlug: string;
}) {
  return <GuideMap locations={locations} activeSlug={activeSlug} />;
}
