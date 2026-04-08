import { getLocations } from "@/lib/notion";
import GuideClient from "./GuideClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "The NV & more Guide | NV & more",
  description: "Our favourite spots in Nordvest — cafés, bars, restaurants, wellness, culture and more.",
};

export const revalidate = 3600;

export default async function GuidePage() {
  const locations = await getLocations();
  return <GuideClient locations={locations} />;
}
