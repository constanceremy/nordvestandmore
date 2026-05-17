"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import type { LocationItem } from "@/lib/notion";

type Props = {
  locations: LocationItem[];
  activeSlug?: string;
};

export default function GuideMap({ locations, activeSlug }: Props) {
  // We intentionally type Leaflet's runtime values loosely — strict typing
  // requires `@types/leaflet` here and would just add noise.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const LRef = useRef<any>(null);
  const [ready, setReady] = useState(false);

  // ── Create the map exactly once ──
  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || mapRef.current) return;
      const container = document.getElementById("guide-map");
      if (!container) return;

      const map = L.map("guide-map").setView([55.704, 12.527], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      const layer = L.layerGroup().addTo(map);

      LRef.current = L;
      mapRef.current = map;
      layerRef.current = layer;
      setReady(true);
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        layerRef.current = null;
      }
    };
  }, []);

  // ── Re-render markers whenever the filtered list (or activeSlug) changes ──
  useEffect(() => {
    if (!ready) return;
    const L = LRef.current;
    const layer = layerRef.current;
    const map = mapRef.current;
    if (!L || !layer || !map) return;

    layer.clearLayers();

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

    const withCoords = locations.filter((l) => l.lat && l.lng);

    withCoords.forEach((loc) => {
      const isActive = loc.slug === activeSlug;
      const marker = L.marker([loc.lat!, loc.lng!], {
        icon: isActive ? activeIcon : icon,
      }).addTo(layer);
      if (!isActive) {
        marker.bindTooltip(loc.name, { permanent: false, direction: "top", offset: [0, -6] });
        marker.on("click", () => {
          window.location.href = `/map/${loc.slug}`;
        });
      }
    });

    // If an activeSlug was passed (location detail page), center on it once
    if (activeSlug) {
      const active = withCoords.find((l) => l.slug === activeSlug);
      if (active) map.setView([active.lat!, active.lng!], 16);
    }
  }, [ready, locations, activeSlug]);

  return (
    <div
      id="guide-map"
      className="w-full h-full"
      style={{ minHeight: "100%", isolation: "isolate" }}
    />
  );
}
