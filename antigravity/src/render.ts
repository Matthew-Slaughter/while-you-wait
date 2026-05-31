// TypeScript port of the shared Python renderer.
// Identical picking logic; rendering adapted to plain-text VS Code surfaces
// (notification toast or OutputChannel) since neither honors ANSI color.

export interface Entry {
  kind: "scripture" | "quote" | "creed" | "prayer";
  text: string;
  ref?: string;
  translation?: string;
  voice?: string;
  insight?: string;
  themes?: string[];
}

const CTRL = /[\x00-\x1f\x7f-\x9f]/g;
function clean(s: string | undefined): string {
  return (s ?? "").replace(CTRL, "");
}

export function entryKey(e: Entry): string {
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

// Compact one-line summary for toast notifications (which truncate aggressively).
export function renderShort(e: Entry): string {
  const text = clean(e.text).trim();
  const ref = clean(e.ref);
  const trans = clean(e.translation);
  const citation = e.kind === "scripture" && trans ? `${ref} (${trans})` : ref;
  const tail = citation || clean(e.voice) || "";
  const truncated = text.length > 140 ? text.slice(0, 137) + "…" : text;
  return `“${truncated}”${tail ? "  — " + tail : ""}`;
}

// Multi-line plain-text rendering for OutputChannel (monospace-friendly).
// Box-drawing characters render in the panel; ANSI color does not.
export function renderFull(e: Entry, width: number = 64): string {
  const inner = width - 4;
  const kind = e.kind ?? "scripture";
  const text = clean(e.text).trim();
  const ref = clean(e.ref);
  const trans = clean(e.translation);
  const insight = clean(e.insight);
  const voice = clean(e.voice);

  const LABELS: Record<string, string> = {
    scripture: "scripture",
    quote: "quote",
    creed: "creed",
    prayer: "prayer",
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
  if (voice && kind !== "scripture" && !citation.includes(voice)) {
    lines.push(`  — ${voice}`);
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
