import { NextResponse } from "next/server";
import { getEvents, getBlogPosts } from "@/lib/notion";

export const revalidate = 3600;

export async function GET() {
  const [events, posts] = await Promise.all([getEvents(true), getBlogPosts()]);

  const eventItems = events.map((e) => ({
    type: e.ownEvent ? "own-event" : "event",
    title: e.title,
    description: e.description || "",
    date: e.date || "",
    location: e.location || "",
    tags: e.tags || [],
    url: e.ownEvent ? `/events/${e.slug}` : e.notionUrl,
    external: !e.ownEvent,
  }));

  const blogItems = posts.map((p) => ({
    type: "blog",
    title: p.title,
    description: p.excerpt || "",
    date: p.publishedDate || "",
    location: "",
    tags: p.tags || [],
    url: `/blog/${p.slug}`,
    external: false,
  }));

  return NextResponse.json([...blogItems, ...eventItems]);
}
