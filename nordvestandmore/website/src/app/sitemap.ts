import type { MetadataRoute } from "next";
import {
  getEvents,
  getBlogPosts,
  getSessions,
  getLocations,
} from "@/lib/notion";

const SITE_URL = "https://nordvestandmore.com";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: SITE_URL, lastModified: now, changeFrequency: "daily", priority: 1.0 },
    { url: `${SITE_URL}/events`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/our-events`, lastModified: now, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE_URL}/blog`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/guide`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];

  const [events, blogPosts, sessions, locations] = await Promise.all([
    getEvents(false).catch(() => []),
    getBlogPosts().catch(() => []),
    getSessions(false).catch(() => []),
    getLocations().catch(() => []),
  ]);

  const eventRoutes: MetadataRoute.Sitemap = events
    .filter((e) => e.ownEvent && e.slug)
    .map((e) => ({
      url: `${SITE_URL}/events/${e.slug}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.7,
    }));

  const blogRoutes: MetadataRoute.Sitemap = blogPosts
    .filter((p) => p.slug)
    .map((p) => ({
      url: `${SITE_URL}/blog/${p.slug}`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    }));

  const sessionRoutes: MetadataRoute.Sitemap = sessions
    .filter((s) => s.id)
    .map((s) => ({
      url: `${SITE_URL}/our-events/${s.id}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.6,
    }));

  const guideRoutes: MetadataRoute.Sitemap = locations
    .filter((l) => l.slug)
    .map((l) => ({
      url: `${SITE_URL}/guide/${l.slug}`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    }));

  return [
    ...staticRoutes,
    ...eventRoutes,
    ...blogRoutes,
    ...sessionRoutes,
    ...guideRoutes,
  ];
}
