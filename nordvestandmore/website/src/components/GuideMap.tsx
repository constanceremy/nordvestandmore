"use client";

import { useEffect } from "react";
import "leaflet/dist/leaflet.css";
import type { LocationItem } from "@/lib/notion";

type Props = {
  locations: LocationItem[];
  activeSlug?: string;
};

export default function GuideMap({ locations, activeSlug }: Props) {
  const withCoords = locations.filter((l) => l.lat && l.lng);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Dynamically import Leaflet to avoid SSR issues
    import("leaflet").then((L) => {
      const container = document.getElementById("guide-map");
      if (!container) return;
      // Destroy existing map instance if any
      if ((container as any)._leaflet_id) return;

      const center: [number, number] = activeSlug
        ? (() => {
            const active = withCoords.find((l) => l.slug === activeSlug);
            return active ? [active.lat!, active.lng!] : [55.704, 12.527];
          })()
        : [55.704, 12.527];

      const map = L.map("guide-map").setView(center, activeSlug ? 16 : 14);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      const icon = L.divIcon({
        className: "",
        html: `<div style="width:10px;height:10px;background:black;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4)"></div>`,
        iconSize: [10, 10],
        iconAnchor: [5, 5],
      });

      const activeIcon = L.divIcon({
        className: "",
        html: `<div style="width:14px;height:14px;background:black;border-radius:50%;border:3px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.6)"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      withCoords.forEach((loc) => {
        const isActive = loc.slug === activeSlug;
        const marker = L.marker([loc.lat!, loc.lng!], {
          icon: isActive ? activeIcon : icon,
        }).addTo(map);
        if (!isActive) {
          marker.bindTooltip(loc.name, { permanent: false, direction: "top", offset: [0, -6] });
          marker.on("click", () => {
            window.location.href = `/guide/${loc.slug}`;
          });
        }
      });
    });
  }, [withCoords, activeSlug]);

  return (
    <div
      id="guide-map"
      className="w-full h-full"
      style={{ minHeight: "100%", isolation: "isolate" }}
    />
  );
}
