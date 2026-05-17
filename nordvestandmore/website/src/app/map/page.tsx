import { getLocations } from "@/lib/notion";
import MapClient from "./MapClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Map of Nordvest | NV & more",
  description:
    "Explore Nordvest on the map — cafés, bars, bakeries, wellness, parks and more, all in one place.",
};

export const revalidate = 3600;

export default async function MapPage() {
  const locations = await getLocations();
  return <MapClient locations={locations} />;
}
