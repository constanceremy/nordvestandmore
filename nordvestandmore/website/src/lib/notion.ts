import { Client } from "@notionhq/client";
import type {
  PageObjectResponse,
} from "@notionhq/client/build/src/api-endpoints";

function getNotion() {
  return new Client({ auth: process.env.NOTION_TOKEN });
}

// ─── Types ────────────────────────────────────────────────────────────────────

export type EventItem = {
  id: string;
  slug: string;
  title: string;
  description: string;
  date: string;
  endDate?: string;
  endTime?: string;
  location: string;
  organizer: string;
  source: string;
  instagramHandle: string;
  sourceType: string;
  price: number;
  currency: string;
  maxSpots: number;
  bookedSpots: number;
  eventType: string;
  tags: string[];
  coverImage?: string;
  isRecurring: boolean;
  recurrenceRule?: string;
  stripeProductId?: string;
  stripePriceId?: string;
  notionUrl: string;
  ownEvent: boolean;
};

export type BlogPost = {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  publishedDate: string;
  coverImage?: string;
  tags: string[];
  author: string;
  notionUrl: string;
  locationIds: string[];
};

export type LocationItem = {
  id: string;
  slug: string;
  name: string;
  tags: string[];
  lat: number | null;
  lng: number | null;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getText(prop: PageObjectResponse["properties"][string]): string {
  if (!prop) return "";
  if (prop.type === "title") return prop.title.map((t) => t.plain_text).join("");
  if (prop.type === "rich_text") return prop.rich_text.map((t) => t.plain_text).join("");
  if (prop.type === "select") return prop.select?.name ?? "";
  if (prop.type === "url") return prop.url ?? "";
  return "";
}

function getNumber(prop: PageObjectResponse["properties"][string]): number {
  if (!prop || prop.type !== "number") return 0;
  return prop.number ?? 0;
}

function getDate(prop: PageObjectResponse["properties"][string]): string {
  if (!prop || prop.type !== "date") return "";
  return prop.date?.start ?? "";
}

function getEndDate(prop: PageObjectResponse["properties"][string]): string | undefined {
  if (!prop || prop.type !== "date") return undefined;
  return prop.date?.end ?? undefined;
}

function getCheckbox(prop: PageObjectResponse["properties"][string]): boolean {
  if (!prop || prop.type !== "checkbox") return false;
  return prop.checkbox;
}

function getMultiSelect(prop: PageObjectResponse["properties"][string]): string[] {
  if (!prop || prop.type !== "multi_select") return [];
  return prop.multi_select.map((s) => s.name);
}

function getFiles(prop: PageObjectResponse["properties"][string]): string | undefined {
  if (!prop || prop.type !== "files") return undefined;
  const file = prop.files[0];
  if (!file) return undefined;
  if (file.type === "external") return file.external.url;
  if (file.type === "file") return file.file.url;
  return undefined;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Converts "7:30pm" or "12:00pm" → "19:30" or "12:00"
function parseTime12h(time: string): string {
  if (!time) return "";
  const match = time.trim().match(/^(\d{1,2}):(\d{2})(am|pm)$/i);
  if (!match) return "";
  let hours = parseInt(match[1]);
  const minutes = match[2];
  const period = match[3].toLowerCase();
  if (period === "pm" && hours !== 12) hours += 12;
  if (period === "am" && hours === 12) hours = 0;
  return `${String(hours).padStart(2, "0")}:${minutes}`;
}

// ─── Events ───────────────────────────────────────────────────────────────────

export async function getEvents(upcoming = true): Promise<EventItem[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_EVENTS_DB_ID!;
  // Use start of today in Copenhagen timezone so today's events aren't filtered out
  const todayCopenhagen = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });

  const filter = upcoming
    ? ({ property: "Start Date", date: { on_or_after: todayCopenhagen } } as const)
    : undefined;

  const deletedFilter = {
    property: "Deleted",
    checkbox: { equals: false },
  };

  const notDuplicateFilter = {
    property: "Possible Duplicate",
    checkbox: { equals: false },
  };

  const approvalFilter = {
    or: [
      { property: "Approved", checkbox: { equals: true } },
      { property: "Own Event", checkbox: { equals: true } },
    ],
  };

  const queryFilter = upcoming
    ? { and: [filter!, deletedFilter, notDuplicateFilter, approvalFilter] }
    : { and: [deletedFilter, notDuplicateFilter, approvalFilter] };

  const allResults: PageObjectResponse[] = [];
  let cursor: string | undefined;
  do {
    const response = await notion.databases.query({
      database_id: dbId,
      filter: queryFilter,
      sorts: [{ property: "Start Date", direction: "ascending" }],
      page_size: 100,
      ...(cursor ? { start_cursor: cursor } : {}),
    });
    allResults.push(...response.results.filter((p): p is PageObjectResponse => p.object === "page"));
    cursor = response.has_more ? (response.next_cursor ?? undefined) : undefined;
  } while (cursor);

  return allResults.map((page) => {
      const p = page.properties;
      const title = getText(p["Event Name"]);
      // Combine Start Date (YYYY-MM-DD) + Start Time (7:30pm) → proper ISO
      const startDate = getDate(p["Start Date"]);
      const startTime = parseTime12h(getText(p["Start Time"]));
      const dateTime = startDate && startTime
        ? `${startDate}T${startTime}:00`
        : startDate;
      return {
        id: page.id,
        slug: getText(p["Slug"]) || slugify(title),
        title,
        description: getText(p["Description"]),
        date: dateTime,
        endDate: getDate(p["End Date"]),
        endTime: getText(p["End Time"]),
        location: getText(p["Location"]),
        organizer: getText(p["Organizer"]),
        source: getText(p["Source"]),
        instagramHandle: getText(p["Instagramhandle"]),
        sourceType: getText(p["Source Type"]),
        price: getNumber(p["Price"]),
        currency: getText(p["Currency"]) || "DKK",
        maxSpots: getNumber(p["Max Spots"]),
        bookedSpots: getNumber(p["Booked Spots"]),
        eventType: getText(p["Source Type"]) || getText(p["Event Type"]),
        tags: getMultiSelect(p["Tag list"]).length > 0 ? getMultiSelect(p["Tag list"]) : getMultiSelect(p["Tags"]).length > 0 ? getMultiSelect(p["Tags"]) : getText(p["Tags"]) ? [getText(p["Tags"])] : [],
        coverImage: getFiles(p["Cover Image"]),
        isRecurring: getText(p["Source Type"]) === "Recurring",
        recurrenceRule: getText(p["Recurrence Rule"]),
        stripeProductId: getText(p["Stripe Product ID"]),
        stripePriceId: getText(p["Stripe Price ID"]),
        notionUrl: getText(p["Event Link"]) || page.url,
        ownEvent: getCheckbox(p["Own Event"]),
      };
    });
}

export async function getEventBySlug(slug: string): Promise<EventItem | null> {
  const all = await getEvents(false);
  return all.find((e) => e.slug === slug) ?? null;
}

// ─── Experiences + Sessions ───────────────────────────────────────────────────

export type BookingPolicy = {
  id: string;
  name: string;
  cancellationWindow: number;
  cancellationTerms: string;
  noShowPolicy: string;
  refundMethod: string;
  minParticipants: number;
  fullPolicyText: string;
};

export type Experience = {
  id: string;
  slug: string;
  name: string;
  description: string;
  shortDescription: string;
  coverImage?: string;
  price: number;
  priceLabel: string;
  currency: string;
  duration: string;
  meetingPoint: string;
  location: string;
  whatsIncluded: string;
  whatToBring: string;
  language: string[];
  tags: string[];
  maxSpots: number;
  stripeProductId?: string;
  bookingPolicyId?: string;
  active: boolean;
  privateOnRequest: boolean;
};

export type Session = {
  id: string;
  date: string;
  startTime: string;
  endTime: string;
  experienceId: string;
  maxSpots: number;
  bookedSpots: number;
  status: string;
  stripePriceId?: string;
  priceOverride?: number;
  notes: string;
  experience?: Experience;
  bookingPolicy?: BookingPolicy;
};

function getRelationId(prop: PageObjectResponse["properties"][string]): string {
  if (!prop || prop.type !== "relation") return "";
  return prop.relation[0]?.id ?? "";
}

function getRelationIds(prop: PageObjectResponse["properties"][string]): string[] {
  if (!prop || prop.type !== "relation") return [];
  return prop.relation.map((r) => r.id);
}

export async function getBookingPolicy(id: string): Promise<BookingPolicy | null> {
  if (!id) return null;
  const notion = getNotion();
  try {
    const page = await notion.pages.retrieve({ page_id: id }) as PageObjectResponse;
    const p = page.properties;
    return {
      id: page.id,
      name: getText(p["Name"]),
      cancellationWindow: getNumber(p["Cancellation window"]),
      cancellationTerms: getText(p["Cancellation terms"]),
      noShowPolicy: getText(p["No-show policy"]),
      refundMethod: getText(p["Refund method"]),
      minParticipants: getNumber(p["Min participants"]),
      fullPolicyText: getText(p["Full policy text"]),
    };
  } catch {
    return null;
  }
}

export async function getExperiences(activeOnly = true): Promise<Experience[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_EXPERIENCES_DB_ID!;

  const response = await notion.databases.query({
    database_id: dbId,
    filter: activeOnly
      ? { property: "Active", checkbox: { equals: true } }
      : undefined,
  });

  return response.results
    .filter((p): p is PageObjectResponse => p.object === "page")
    .map((page) => {
      const p = page.properties;
      const name = getText(p["Name"]);
      return {
        id: page.id,
        slug: getText(p["Slug"]) || slugify(name),
        name,
        description: getText(p["Description"]),
        shortDescription: getText(p["Short description"]),
        coverImage: getFiles(p["Cover image"]),
        price: getNumber(p["Price"]),
        priceLabel: getText(p["Price label"]),
        currency: getText(p["Currency"]) || "DKK",
        duration: getText(p["Duration"]),
        meetingPoint: getText(p["Meeting point"]),
        location: getText(p["Location"]),
        whatsIncluded: getText(p["What's included"]),
        whatToBring: getText(p["What to bring"]),
        language: getMultiSelect(p["Language"]),
        tags: getMultiSelect(p["Tags"]),
        maxSpots: getNumber(p["Max spots"]),
        stripeProductId: getText(p["Stripe Product ID"]),
        bookingPolicyId: getRelationId(p["Booking policy"]),
        active: getCheckbox(p["Active"]),
        privateOnRequest: getCheckbox(p["Private / On Request"]),
      };
    });
}

export async function getPrivateExperiences(): Promise<Experience[]> {
  const all = await getExperiences(true);
  return all.filter((e) => e.privateOnRequest);
}

export async function getSessions(upcomingOnly = true): Promise<Session[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_SESSIONS_DB_ID!;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });

  const response = await notion.databases.query({
    database_id: dbId,
    filter: upcomingOnly
      ? {
          and: [
            { property: "Date", date: { on_or_after: today } },
            { property: "Status", select: { does_not_equal: "Cancelled" } },
            { property: "Hidden", checkbox: { equals: false } },
          ],
        }
      : undefined,
    sorts: [{ property: "Date", direction: "ascending" }],
  });

  const sessions = response.results
    .filter((p): p is PageObjectResponse => p.object === "page")
    .map((page) => {
      const p = page.properties;
      const priceOverrideRaw = getNumber(p["Price override"]);
      return {
        id: page.id,
        date: getDate(p["Date"]),
        startTime: getText(p["Start time"]),
        endTime: getText(p["End time"]),
        experienceId: getRelationId(p["Experience"]),
        maxSpots: getNumber(p["Max spots"]),
        bookedSpots: getNumber(p["Booked spots"]),
        status: getText(p["Status"]),
        stripePriceId: getText(p["Stripe Price ID"]) || undefined,
        priceOverride: priceOverrideRaw > 0 ? priceOverrideRaw : undefined,
        notes: getText(p["Notes"]),
      };
    });

  // Join experiences
  const experiences = await getExperiences();
  const expMap = new Map(experiences.map((e) => [e.id, e]));

  // Join booking policies
  const policyIds = [...new Set(
    experiences.map((e) => e.bookingPolicyId).filter(Boolean) as string[]
  )];
  const policies = await Promise.all(policyIds.map(getBookingPolicy));
  const policyMap = new Map(
    policies.filter(Boolean).map((p) => [p!.id, p!])
  );

  return sessions.map((s) => {
    const exp = expMap.get(s.experienceId);
    return {
      ...s,
      experience: exp,
      bookingPolicy: exp?.bookingPolicyId ? policyMap.get(exp.bookingPolicyId) : undefined,
    };
  });
}

export async function getSessionById(id: string): Promise<Session | null> {
  const all = await getSessions(false);
  return all.find((s) => s.id === id) ?? null;
}

// ─── Blog ─────────────────────────────────────────────────────────────────────

export async function getBlogPosts(): Promise<BlogPost[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_BLOG_DB_ID!;

  const response = await notion.databases.query({
    database_id: dbId,
    filter: {
      property: "Published",
      checkbox: { equals: true },
    },
    sorts: [{ property: "Published Date", direction: "descending" }],
  });

  return response.results
    .filter((p): p is PageObjectResponse => p.object === "page")
    .map((page) => {
      const p = page.properties;
      const title = getText(p["Name"] ?? p["Title"]);
      return {
        id: page.id,
        slug: getText(p["Slug"]) || slugify(title),
        title,
        excerpt: getText(p["Excerpt"]),
        publishedDate: getDate(p["Published Date"]) || page.created_time,
        coverImage: getFiles(p["Cover Image"]),
        tags: getMultiSelect(p["Tags"]),
        author: getText(p["Author"]) || "NV & more",
        notionUrl: page.url,
        locationIds: getRelationIds(p["Locations"]),
      };
    })
    .sort((a, b) => b.publishedDate.localeCompare(a.publishedDate));
}

export async function getBlogPostBySlug(slug: string): Promise<BlogPost | null> {
  const all = await getBlogPosts();
  return all.find((p) => p.slug === slug) ?? null;
}

export async function getPageBlocks(pageId: string) {
  const notion = getNotion();
  const response = await notion.blocks.children.list({ block_id: pageId });
  return response.results;
}

// ─── Locations ────────────────────────────────────────────────────────────────

export async function getLocations(): Promise<LocationItem[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_LOCATIONS_DB_ID!;

  const allResults: PageObjectResponse[] = [];
  let cursor: string | undefined;
  do {
    const response = await notion.databases.query({
      database_id: dbId,
      page_size: 100,
      filter: { property: "Published Location", checkbox: { equals: true } },
      sorts: [{ property: "Name", direction: "ascending" }],
      ...(cursor ? { start_cursor: cursor } : {}),
    });
    allResults.push(...response.results.filter((p): p is PageObjectResponse => p.object === "page"));
    cursor = response.has_more ? (response.next_cursor ?? undefined) : undefined;
  } while (cursor);

  return allResults
    .map((page) => {
      const p = page.properties;
      const name = getText(p["Name"]);
      const latStr = getText(p["Lat"]);
      const lngStr = getText(p["Lng"]);
      return {
        id: page.id,
        slug: slugify(name),
        name,
        tags: getMultiSelect(p["Tags"]),
        lat: latStr ? parseFloat(latStr) : null,
        lng: lngStr ? parseFloat(lngStr) : null,
      };
    })
    .filter((l) => l.name);
}

export async function getLocationBySlug(slug: string): Promise<LocationItem | null> {
  const all = await getLocations();
  return all.find((l) => l.slug === slug) ?? null;
}

export async function getEventsByLocation(locationId: string): Promise<EventItem[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_EVENTS_DB_ID!;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Copenhagen" });

  const response = await notion.databases.query({
    database_id: dbId,
    filter: {
      and: [
        { property: "Locations", relation: { contains: locationId } },
        { property: "Start Date", date: { on_or_after: today } },
        { property: "Deleted", checkbox: { equals: false } },
        {
          or: [
            { property: "Approved", checkbox: { equals: true } },
            { property: "Own Event", checkbox: { equals: true } },
          ],
        },
      ],
    },
    sorts: [{ property: "Start Date", direction: "ascending" }],
  });

  return response.results
    .filter((p): p is PageObjectResponse => p.object === "page")
    .map((page) => {
      const p = page.properties;
      const title = getText(p["Event Name"]);
      const startDate = getDate(p["Start Date"]);
      const startTime = parseTime12h(getText(p["Start Time"]));
      const dateTime = startDate && startTime ? `${startDate}T${startTime}:00` : startDate;
      return {
        id: page.id,
        slug: getText(p["Slug"]) || slugify(title),
        title,
        description: getText(p["Description"]),
        date: dateTime,
        endDate: getDate(p["End Date"]),
        endTime: getText(p["End Time"]),
        location: getText(p["Location"]),
        organizer: getText(p["Organizer"]),
        source: getText(p["Source"]),
        instagramHandle: getText(p["Instagramhandle"]),
        sourceType: getText(p["Source Type"]),
        price: getNumber(p["Price"]),
        currency: getText(p["Currency"]) || "DKK",
        maxSpots: getNumber(p["Max Spots"]),
        bookedSpots: getNumber(p["Booked Spots"]),
        eventType: getText(p["Source Type"]) || getText(p["Event Type"]),
        tags: getMultiSelect(p["Tag list"]).length > 0 ? getMultiSelect(p["Tag list"]) : getMultiSelect(p["Tags"]).length > 0 ? getMultiSelect(p["Tags"]) : getText(p["Tags"]) ? [getText(p["Tags"])] : [],
        coverImage: getFiles(p["Cover Image"]),
        isRecurring: getText(p["Source Type"]) === "Recurring",
        recurrenceRule: getText(p["Recurrence Rule"]),
        stripeProductId: getText(p["Stripe Product ID"]),
        stripePriceId: getText(p["Stripe Price ID"]),
        notionUrl: getText(p["Event Link"]) || page.url,
        ownEvent: getCheckbox(p["Own Event"]),
      };
    });
}

export async function getBlogPostsByLocation(locationId: string): Promise<BlogPost[]> {
  const notion = getNotion();
  const dbId = process.env.NOTION_BLOG_DB_ID!;

  const response = await notion.databases.query({
    database_id: dbId,
    filter: {
      and: [
        { property: "Locations", relation: { contains: locationId } },
        { property: "Published", checkbox: { equals: true } },
      ],
    },
    sorts: [{ property: "Published Date", direction: "descending" }],
  });

  return response.results
    .filter((p): p is PageObjectResponse => p.object === "page")
    .map((page) => {
      const p = page.properties;
      const title = getText(p["Name"] ?? p["Title"]);
      return {
        id: page.id,
        slug: getText(p["Slug"]) || slugify(title),
        title,
        excerpt: getText(p["Excerpt"]),
        publishedDate: getDate(p["Published Date"]) || page.created_time,
        coverImage: getFiles(p["Cover Image"]),
        tags: getMultiSelect(p["Tags"]),
        author: getText(p["Author"]) || "NV & more",
        notionUrl: page.url,
        locationIds: getRelationIds(p["Locations"]),
      };
    });
}
