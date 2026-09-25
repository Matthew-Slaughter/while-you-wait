// TypeScript port of the shared Python renderer.
// Identical picking logic; rendering adapted to plain-text VS Code surfaces
// (notification toast or OutputChannel) since neither honors ANSI color.
//
// Schema v2 (see docs/PLAN-0.5.md): `kind` gains "hymn"; entries gain
// optional `id`, `witness`, `source`, `added`. Rendering rules:
//   - hymn renders like a quote (ref line, then voice line)
//   - a quote with source "attributed" renders its voice line as
//     "— attributed to <voice>"
// Nothing else changes.

export type Kind = "scripture" | "quote" | "creed" | "prayer" | "hymn";

export const ALL_KINDS: Kind[] = ["scripture", "quote", "creed", "prayer", "hymn"];

export interface Witness {
  voice?: string;
  work?: string;
  source?: string;
  path?: string;
  quote?: string;
}

export interface Entry {
  kind: Kind;
  text: string;
  ref?: string;
  translation?: string;
  voice?: string;
  insight?: string;
  themes?: string[];
  // --- schema v2 (all optional so v1 corpora still type-check) ---
  id?: string;
  witness?: Witness;
  source?: "primary" | "attributed"; // quotes only
  added?: string;
}

// Strip control characters but keep newlines: hymn stanzas and prayers are
// multi-line, and renderFull wraps each line separately.
const CTRL = /[\x00-\x09\x0b-\x1f\x7f-\x9f]/g;
function clean(s: string | undefined): string {
  return (s ?? "").replace(CTRL, "");
}

// Anti-repeat key. Mirrors the Python renderer's entry_key(): use the stable
// `id` when present (schema v2), else the legacy kind|ref|text[:40] key.
export function entryKey(e: Entry): string {
  if (typeof e.id === "string" && e.id.length > 0) return e.id;
  return `${e.kind ?? ""}|${e.ref ?? ""}|${(e.text ?? "").slice(0, 40)}`;
}

// Anti-repeat random pick: skip entries whose key appears in the recent window,
// fall back to the full pool if the window covers everything (tiny corpora).
export function pickEntry(entries: Entry[], recent: string[]): Entry {
  const recentSet = new Set(recent);
  const candidates = entries.filter((e) => !recentSet.has(entryKey(e)));
  const pool = candidates.length > 0 ? candidates : entries;
  return pool[Math.floor(Math.random() * pool.length)];
}

// Voice line as it should be attributed. Quotes with source "attributed"
// are marked so; everything else uses the voice verbatim.
function attributedVoice(e: Entry): string {
  const voice = clean(e.voice).trim();
  if (!voice) return "";
  if (e.kind === "quote" && e.source === "attributed") {
    return `attributed to ${voice}`;
  }
  return voice;
}

// Compact one-line summary for toast notifications (which truncate aggressively).
export function renderShort(e: Entry): string {
  // One-line surface: fold stanza/paragraph breaks into " / ".
  const text = clean(e.text).trim().replace(/\s*\n+\s*/g, " / ");
  const ref = clean(e.ref);
  const trans = clean(e.translation);
  const citation = e.kind === "scripture" && trans ? `${ref} (${trans})` : ref;
  const tail = citation || attributedVoice(e) || "";
  const truncated = text.length > 140 ? text.slice(0, 137) + "…" : text;
  return `“${truncated}”${tail ? "  — " + tail : ""}`;
}

// Multi-line plain-text rendering for OutputChannel (monospace-friendly).
// Box-drawing characters render in the panel; ANSI color does not.
export function renderFull(e: Entry, width: number = 64): string {
  const inner = width - 4;
  const kind: string = e.kind ?? "scripture";
  const text = clean(e.text).trim();
  const ref = clean(e.ref);
  const trans = clean(e.translation);
  const insight = clean(e.insight);
  const voice = clean(e.voice).trim();

  const LABELS: Record<string, string> = {
    scripture: "scripture",
    quote: "quote",
    creed: "creed",
    prayer: "prayer",
    hymn: "hymn",
  };
  const label = LABELS[kind] ?? "scripture";
  const citation =
    kind === "scripture" && trans ? `${ref} (${trans})` : ref;

  const top = `╭─── while you wait · ${label} ${"─".repeat(
    Math.max(3, width - 24 - label.length),
  )}╮`;
  const bot = `╰${"─".repeat(width - 2)}╯`;

  const lines: string[] = [top, ""];
  for (const w of wrap(`“${text}”`, inner)) lines.push(`  ${w}`);
  if (citation) lines.push(`  — ${citation}`);
  if (insight) {
    lines.push("");
    for (const w of wrap(insight, inner)) lines.push(`  ${w}`);
  }
  // Voice line: quotes, creeds, prayers and hymns (hymn renders like a quote).
  if (voice && kind !== "scripture" && !citation.includes(voice)) {
    lines.push(`  — ${attributedVoice(e)}`);
  }
  lines.push("");
  lines.push(bot);
  return lines.join("\n");
}

function wrap(s: string, width: number): string[] {
  const out: string[] = [];
  for (const para of s.split("\n")) {
    const words = para.split(/\s+/).filter(Boolean);
    let line = "";
    for (const w of words) {
      if (line.length === 0) {
        line = w;
      } else if (line.length + 1 + w.length <= width) {
        line += " " + w;
      } else {
        out.push(line);
        line = w;
      }
    }
    if (line) out.push(line);
  }
  if (out.length === 0) out.push("");
  return out;
}
