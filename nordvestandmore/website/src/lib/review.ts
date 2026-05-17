import { Client } from "@notionhq/client";
import type { PageObjectResponse } from "@notionhq/client/build/src/api-endpoints";
import { similarity, sourcePriority } from "./similarity";

export type ReviewEvent = {
  id: string;
  notionUrl: string;
  title: string;
  description: string;
  startTime: string;
  endTime: string;
  location: string;
  organizer: string;
  sourceType: string;
  eventLink: string;
  sourceUrl: string;
  igHandle: string;
  price: number | null;
  maxSpots: number | null;
  tagList: string[];
  tagsLegacy: string[];
  coverImage: string | null;
  ownEvent: boolean;
};

function getNotion() {
  return new Client({ auth: process.env.NOTION_TOKEN });
}

// ─── Property readers ────────────────────────────────────────────────────────

function getText(prop: PageObjectResponse["properties"][string] | undefined): string {
  if (!prop) return "";
  if (prop.type === "title") return prop.title.map((t) => t.plain_text).join("");
  if (prop.type === "rich_text") return prop.rich_text.map((t) => t.plain_text).join("");
  if (prop.type === "url") return prop.url ?? "";
  if (prop.type === "select") return prop.select?.name ?? "";
  return "";
}

function getNumber(prop: PageObjectResponse["properties"][string] | undefined): number | null {
  if (!prop || prop.type !== "number") return null;
  return prop.number ?? null;
}

function getMulti(prop: PageObjectResponse["properties"][string] | undefined): string[] {
  if (!prop || prop.type !== "multi_select") return [];
  return prop.multi_select.map((s) => s.name);
}

function getCover(prop: PageObjectResponse["properties"][string] | undefined): string | null {
  if (!prop || prop.type !== "files") return null;
  const f = prop.files[0];
  if (!f) return null;
  if (f.type === "external") return f.external.url;
  if (f.type === "file") return f.file.url;
  return null;
}

function getCheckbox(prop: PageObjectResponse["properties"][string] | undefined): boolean {
  if (!prop || prop.type !== "checkbox") return false;
  return prop.checkbox;
}

function parsePage(page: PageObjectResponse): ReviewEvent {
  const p = page.properties;
  return {
    id: page.id,
    notionUrl: page.url,
    title: getText(p["Event Name"]),
    description: getText(p["Description"]),
    startTime: getText(p["Start Time"]),
    endTime: getText(p["End Time"]),
    location: getText(p["Location"]),
    organizer: getText(p["Organizer"]),
    sourceType: getText(p["Source Type"]),
    eventLink: getText(p["Event Link"]),
    sourceUrl: getText(p["Source"]),
    igHandle: getText(p["Instagramhandle"]),
    price: getNumber(p["Price"]),
    maxSpots: getNumber(p["Max Spots"]),
    tagList: getMulti(p["Tag List"]),
    tagsLegacy: getMulti(p["Tags"]),
    coverImage: getCover(p["Cover Image"]),
    ownEvent: getCheckbox(p["Own Event"]),
  };
}

// ─── Fetch ───────────────────────────────────────────────────────────────────

export async function getEventsForDate(isoDate: string): Promise<ReviewEvent[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_EVENTS_DB_ID!;
  const events: ReviewEvent[] = [];
  let cursor: string | undefined;
  do {
    const resp = await notion.databases.query({
      database_id: dbId,
      page_size: 100,
      filter: { property: "Start Date", date: { equals: isoDate } },
      sorts: [{ property: "Start Time", direction: "ascending" }],
      ...(cursor ? { start_cursor: cursor } : {}),
    });
    for (const page of resp.results) {
      if (page.object === "page") events.push(parsePage(page as PageObjectResponse));
    }
    cursor = resp.has_more ? (resp.next_cursor ?? undefined) : undefined;
  } while (cursor);
  return events;
}

// ─── Clustering ──────────────────────────────────────────────────────────────

export function clusterEvents(events: ReviewEvent[], threshold = 0.65): ReviewEvent[][] {
  const n = events.length;
  const parent = Array.from({ length: n }, (_, i) => i);

  function find(i: number): number {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  }

  function union(i: number, j: number) {
    const ri = find(i);
    const rj = find(j);
    if (ri !== rj) parent[ri] = rj;
  }

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (similarity(events[i].title, events[j].title) >= threshold) {
        union(i, j);
      }
    }
  }

  const groups = new Map<number, ReviewEvent[]>();
  for (let i = 0; i < n; i++) {
    const r = find(i);
    if (!groups.has(r)) groups.set(r, []);
    groups.get(r)!.push(events[i]);
  }
  return [...groups.values()];
}

export function linkFor(e: ReviewEvent): string {
  return e.eventLink || e.sourceUrl || "";
}

export function eventSourcePriority(e: ReviewEvent): number {
  return sourcePriority(linkFor(e));
}

// ─── Merge engine ────────────────────────────────────────────────────────────

export type MergePlan = {
  winnerId: string;
  loserIds: string[];
  title: string;
  description: string;
  startTime: string;
  endTime: string;
  location: string;
  organizer: string;
  eventLink: string;
  tagList: string[];
  price: number | null;
  maxSpots: number | null;
  coverImage: string | null;
};

function fillScore(e: ReviewEvent): number {
  let s = 0;
  if (e.description) s++;
  if (e.location) s++;
  if (e.organizer) s++;
  if (e.startTime) s++;
  if (e.endTime) s++;
  if (e.eventLink) s++;
  if (e.coverImage) s++;
  if (e.maxSpots !== null) s++;
  if (e.price !== null) s++;
  if (e.tagList.length) s++;
  return s;
}

export function computeMergePlan(cluster: ReviewEvent[]): MergePlan {
  const sorted = [...cluster].sort((a, b) => {
    const pa = eventSourcePriority(a);
    const pb = eventSourcePriority(b);
    if (pa !== pb) return pa - pb;
    return fillScore(b) - fillScore(a);
  });
  const winner = sorted[0];
  const losers = sorted.slice(1);

  // Title: pick longest distinct title (Gemini optional, not wired by default)
  const distinctTitles = [...new Set(sorted.map((e) => e.title.trim()).filter(Boolean))];
  const mergedTitle = distinctTitles.length <= 1
    ? distinctTitles[0] || winner.title
    : distinctTitles.reduce((a, b) => (a.length >= b.length ? a : b));

  // Tag List: union across cluster, with legacy Tags as fallback per event
  const mergedTags: string[] = [];
  for (const e of sorted) {
    const source = e.tagList.length ? e.tagList : e.tagsLegacy;
    for (const t of source) {
      if (t && !mergedTags.includes(t)) mergedTags.push(t);
    }
  }

  // Pick best link by source priority
  const linkCandidates = [...sorted].sort(
    (a, b) => sourcePriority(linkFor(a)) - sourcePriority(linkFor(b))
  );
  const mergedLink = linkCandidates.map(linkFor).find(Boolean) || "";

  const longestNonEmpty = (key: "description" | "location" | "organizer"): string => {
    const vals = sorted.map((e) => e[key]).filter(Boolean);
    return vals.length ? vals.reduce((a, b) => (a.length >= b.length ? a : b)) : "";
  };

  const firstNonEmpty = <T>(vals: T[]): T | null => {
    for (const v of vals) if (v) return v;
    return null;
  };

  return {
    winnerId: winner.id,
    loserIds: losers.map((l) => l.id),
    title: mergedTitle,
    description: longestNonEmpty("description"),
    startTime: firstNonEmpty(sorted.map((e) => e.startTime)) || "",
    endTime: firstNonEmpty(sorted.map((e) => e.endTime)) || "",
    location: longestNonEmpty("location"),
    organizer: longestNonEmpty("organizer"),
    eventLink: mergedLink,
    tagList: mergedTags,
    price: firstNonEmpty(sorted.map((e) => e.price)),
    maxSpots: firstNonEmpty(sorted.map((e) => e.maxSpots)),
    coverImage: firstNonEmpty(sorted.map((e) => e.coverImage)),
  };
}

// ─── Apply merge to Notion ───────────────────────────────────────────────────

export async function applyMerge(plan: MergePlan): Promise<void> {
  const notion = getNotion();

  // 1. Patch winner with merged values
  const props: Record<string, unknown> = {
    "Event Name": { title: [{ text: { content: plan.title } }] },
    "Tag List": { multi_select: plan.tagList.map((t) => ({ name: t })) },
  };
  if (plan.description) props["Description"] = { rich_text: [{ text: { content: plan.description } }] };
  if (plan.startTime) props["Start Time"] = { rich_text: [{ text: { content: plan.startTime } }] };
  if (plan.endTime) props["End Time"] = { rich_text: [{ text: { content: plan.endTime } }] };
  if (plan.location) props["Location"] = { rich_text: [{ text: { content: plan.location } }] };
  if (plan.organizer) props["Organizer"] = { rich_text: [{ text: { content: plan.organizer } }] };
  if (plan.eventLink) props["Event Link"] = { url: plan.eventLink };
  if (plan.price !== null) props["Price"] = { number: plan.price };
  if (plan.maxSpots !== null) props["Max Spots"] = { number: plan.maxSpots };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await notion.pages.update({ page_id: plan.winnerId, properties: props as any });

  // 2. Archive losers (soft delete; restorable for 30 days)
  for (const loserId of plan.loserIds) {
    await notion.pages.update({ page_id: loserId, archived: true });
  }
}
