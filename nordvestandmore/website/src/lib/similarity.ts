// Ported from nordvestandmore/scraper/dedup.py — keep behaviour close.

const DANISH_MONTHS_RE =
  /\s*[-–]\s*\d{1,2}\.?\s*(jan(uar)?|feb(ruar)?|mar(ts)?|apr(il)?|maj|jun[ie]?|jul[ie]?|aug(ust)?|sep(tember)?|okt(ober)?|nov(ember)?|dec(ember)?)\.?\s*$/i;

export function normalizeText(text: string): string {
  let t = text.toLowerCase().trim();
  t = t.replace(DANISH_MONTHS_RE, "");
  t = t.replace(/[^\w\s]/g, " ");
  t = t.replace(/\s+/g, " ");
  return t.trim();
}

function stripDateSuffix(text: string): string {
  return text.toLowerCase().trim().replace(DANISH_MONTHS_RE, "");
}

function compress(text: string): string {
  return stripDateSuffix(text).replace(/[^a-zæøå0-9]/g, "");
}

function trigrams(text: string): Set<string> {
  const t = compress(text);
  if (t.length < 3) return t ? new Set([t]) : new Set();
  const out = new Set<string>();
  for (let i = 0; i < t.length - 2; i++) out.add(t.slice(i, i + 3));
  return out;
}

function jaccard<T>(a: Set<T>, b: Set<T>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  return inter / (a.size + b.size - inter);
}

export function similarity(a: string, b: string): number {
  if (!a || !b) return 0;

  // Word-level Jaccard
  const wordsA = new Set(normalizeText(a).split(" ").filter(Boolean));
  const wordsB = new Set(normalizeText(b).split(" ").filter(Boolean));
  const wordSim = jaccard(wordsA, wordsB);

  // Compressed containment
  const ca = compress(a);
  const cb = compress(b);
  let containment = 0;
  if (ca && cb) {
    const [shorter, longer] = ca.length <= cb.length ? [ca, cb] : [cb, ca];
    if (longer.includes(shorter)) {
      containment = shorter.length / longer.length;
      if (containment >= 0.4) {
        containment = Math.max(containment, 0.85);
      } else if (shorter.length >= 8 && longer.startsWith(shorter)) {
        containment = 0.9;
      } else if (shorter.length >= 8 && containment >= 0.2) {
        containment = Math.max(containment, 0.8);
      }
    }
  }

  // Trigram Jaccard
  const trigramSim = jaccard(trigrams(a), trigrams(b));

  return Math.max(wordSim, containment, trigramSim);
}

// Source-priority for choosing which link/winner survives in a merge.
// Lower = better. 1=website, 2=facebook, 3=instagram.
export function sourcePriority(url: string): number {
  const u = (url || "").toLowerCase();
  if (u.includes("instagram.com")) return 3;
  if (u.includes("facebook.com")) return 2;
  return 1;
}
