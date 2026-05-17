import { notFound } from "next/navigation";
import { clusterEvents, getEventsForDate } from "@/lib/review";
import ReviewClient from "./ReviewClient";

export const dynamic = "force-dynamic"; // always fresh, no cache

function tomorrowISO(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function isValidDate(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(new Date(s).getTime());
}

export default async function AdminReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ date?: string }>;
}) {
  const { token } = await params;
  const expected = process.env.ADMIN_TOKEN;
  if (!expected || token !== expected) notFound();

  const sp = await searchParams;
  const date = sp.date && isValidDate(sp.date) ? sp.date : tomorrowISO();

  const events = await getEventsForDate(date);
  const clusters = clusterEvents(events, 0.65);
  const singletons = clusters.filter((c) => c.length === 1).flat();
  const duplicates = clusters.filter((c) => c.length > 1);

  return (
    <ReviewClient
      token={token}
      date={date}
      singletons={singletons}
      duplicates={duplicates}
    />
  );
}
