import { NextResponse } from "next/server";
import { Client } from "@notionhq/client";
import type { PageObjectResponse } from "@notionhq/client/build/src/api-endpoints";
import { applyMerge, computeMergePlan, type ReviewEvent } from "@/lib/review";

export const dynamic = "force-dynamic";

function getNotion() {
  return new Client({ auth: process.env.NOTION_TOKEN });
}

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

export async function POST(req: Request) {
  const expected = process.env.ADMIN_TOKEN;
  if (!expected) {
    return NextResponse.json({ error: "ADMIN_TOKEN not configured" }, { status: 500 });
  }

  let body: { token?: string; eventIds?: string[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }

  if (body.token !== expected) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  if (!Array.isArray(body.eventIds) || body.eventIds.length < 2) {
    return NextResponse.json({ error: "Need at least 2 eventIds" }, { status: 400 });
  }

  const notion = getNotion();
  const events: ReviewEvent[] = [];
  for (const id of body.eventIds) {
    try {
      const page = (await notion.pages.retrieve({ page_id: id })) as PageObjectResponse;
      events.push(parsePage(page));
    } catch (e) {
      return NextResponse.json(
        { error: `Failed to fetch event ${id}: ${(e as Error).message}` },
        { status: 500 }
      );
    }
  }

  const plan = computeMergePlan(events);

  try {
    await applyMerge(plan);
  } catch (e) {
    return NextResponse.json(
      { error: `Merge failed: ${(e as Error).message}` },
      { status: 500 }
    );
  }

  return NextResponse.json({
    ok: true,
    winnerId: plan.winnerId,
    loserIds: plan.loserIds,
    merged: { title: plan.title, tagList: plan.tagList, eventLink: plan.eventLink },
  });
}
