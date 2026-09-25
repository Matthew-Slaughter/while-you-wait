#!/usr/bin/env python3
"""ingest-creeds.py: emit creed/catechism entries from NonlinearFruit/Creeds.json.

Reads sources/Creeds.json/creeds/*.json and writes corpus/incoming/creeds.json.

Rules (see docs/PLAN-0.5.md and docs/SOURCES.md):
  * only documents whose Metadata.SourceAttribution is exactly "Public Domain";
  * never the eight copyrighted documents listed in EXCLUDED_FILES;
  * primary text is copied verbatim; the only change is whitespace
    normalization (runs of whitespace collapsed to a single space);
  * any item whose text exceeds MAX_CHARS is skipped and reported;
  * insight is "" and themes is [] for a later humanize pass.

Usage:
  python3 scripts/ingest-creeds.py [--target 700] [--out corpus/incoming/creeds.json] [-v]
"""
import argparse

# Source metadata credits single authors to committee documents; hedge them.
AUTHOR_OVERRIDES = {"heidelberg_catechism": "Zacharias Ursinus (principal author; Heidelberg committee, 1563)"}
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "sources", "Creeds.json", "creeds")
DEFAULT_OUT = os.path.join(ROOT, "corpus", "incoming", "creeds.json")
SOURCE_SLUG = "NonlinearFruit/Creeds.json"
ADDED = "0.6.0"
MAX_CHARS = 700

# Copyrighted documents (per the repo README); never ingested regardless of metadata.
EXCLUDED_FILES = {
    "chicago_statement_on_biblical_inerrancy",
    "christ_hymn_of_colossians",
    "christ_hymn_of_philippians",
    "christian_shema",
    "confession_of_peter",
    "helvetic_consensus",
    "savoy_declaration",
    "shema_yisrael",
}

# (file stem, id slug, ref title). CORE docs are always ingested in full;
# FILL docs are added in order, one unit (chapter / article / Q&A) at a time,
# until the running total reaches --target.
CORE = [
    ("westminster_shorter_catechism", "wsc", "Westminster Shorter Catechism"),
    ("heidelberg_catechism", "hc", "Heidelberg Catechism"),
    ("1695_baptist_catechism", "bc1695", "1695 Baptist Catechism"),
    ("apostles_creed", "apc", "Apostles' Creed"),
    ("nicene_creed", "nic", "Nicene Creed"),
    ("athanasian_creed", "ath", "Athanasian Creed"),
    ("chalcedonian_definition", "chal", "Chalcedonian Definition"),
]
FILL = [
    ("westminster_confession_of_faith", "wcf", "Westminster Confession of Faith"),
    ("belgic_confession_of_faith", "bel", "Belgic Confession"),
    ("canons_of_dort", "dort", "Canons of Dort"),
    ("london_baptist_1689", "lbc", "1689 London Baptist Confession"),
    # The plan also names the 39 Articles, the Augsburg Confession and Luther's
    # Small Catechism; none of them is in Creeds.json (see WANTED_BUT_ABSENT).
    ("westminster_larger_catechism", "wlc", "Westminster Larger Catechism"),
]
WANTED_BUT_ABSENT = ["Thirty-Nine Articles", "Augsburg Confession", "Luther's Small Catechism"]

_WS = re.compile(r"\s+")


def norm_ws(s):
    return _WS.sub(" ", s).strip()


def split_long(text, limit=MAX_CHARS):
    """Split a creed at its natural breaks: paragraphs first, then sentences.

    Nothing is reworded; every chunk is a contiguous, verbatim slice of the
    paragraph it came from.
    """
    parts = []
    for para in [p for p in re.split(r"\n\s*\n", text) if p.strip()]:
        para = norm_ws(para)
        if len(para) <= limit:
            parts.append(para)
            continue
        sentences = re.split(r"(?<=[.;:!?])\s+", para)
        buf = ""
        for s in sentences:
            cand = (buf + " " + s).strip() if buf else s
            if len(cand) <= limit:
                buf = cand
            else:
                if buf:
                    parts.append(buf)
                buf = s
        if buf:
            parts.append(buf)
    return parts


def authors_of(meta, title, fname=""):
    stem = os.path.splitext(os.path.basename(fname))[0] if fname else ""
    if stem in AUTHOR_OVERRIDES:
        return AUTHOR_OVERRIDES[stem]
    a = [x for x in meta.get("Authors") or [] if x]
    if not a:
        return title
    if len(a) > 4:
        return ", ".join(a[:3]) + " et al."
    return ", ".join(a)


def load_doc(stem):
    path = os.path.join(SRC_DIR, stem + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def eligible(stem, doc):
    if stem in EXCLUDED_FILES:
        return False, "in EXCLUDED_FILES"
    attr = (doc.get("Metadata") or {}).get("SourceAttribution")
    if attr != "Public Domain":
        return False, "SourceAttribution is %r, not 'Public Domain'" % attr
    return True, ""


def make_entry(eid, ref, text, voice, witness):
    return {
        "id": eid,
        "kind": "creed",
        "ref": ref,
        "text": text,
        "voice": voice,
        "insight": "",
        "witness": witness,
        "themes": [],
        "added": ADDED,
    }


def units_for(stem, slug, title, doc):
    """Yield (unit_key, [entries], [skips]) for a document.

    A unit is a chapter (confessions), an article (canons) or one Q&A / one
    creed (catechisms, creeds). Skips are (ref, chars) tuples.
    """
    meta = doc["Metadata"]
    fmt = meta.get("CreedFormat")
    year = meta.get("Year")
    voice_w = authors_of(meta, title, "creeds/%s.json" % stem)
    work = "%s (%s)" % (title, year) if year else title
    fname = "creeds/%s.json" % stem

    def witness(frag):
        return {
            "voice": voice_w,
            "work": work,
            "source": SOURCE_SLUG,
            "path": fname + ("#" + frag if frag else ""),
            "quote": "",
        }

    data = doc["Data"]
    if fmt == "Creed":
        content = data["Content"]
        whole = norm_ws(content)
        if len(whole) <= MAX_CHARS:
            yield "whole", [make_entry("cat-%s-001" % slug, title, whole, title, witness(""))], []
        else:
            parts = split_long(content)
            entries, skips = [], []
            for i, p in enumerate(parts, 1):
                ref = "%s, art. %d" % (title, i)
                if len(p) > MAX_CHARS:
                    skips.append((ref, len(p)))
                    continue
                entries.append(make_entry("cat-%s-%03d" % (slug, i), ref, p, title, witness("art.%d" % i)))
            yield "whole", entries, skips
    elif fmt == "Catechism":
        for item in data:
            n = int(item["Number"])
            ref = "%s, Q&A %d" % (title, n)
            if not norm_ws(item.get("Answer") or "") or not norm_ws(item.get("Question") or ""):
                yield n, [], [(ref + " (empty question or answer in source)", 0)]
                continue
            text = "Q. %s A. %s" % (norm_ws(item["Question"]), norm_ws(item["Answer"]))
            if len(text) > MAX_CHARS:
                yield n, [], [(ref, len(text))]
                continue
            yield n, [make_entry("cat-%s-%03d" % (slug, n), ref, text, title, witness(str(n)))], []
    elif fmt == "Confession":  # chapters with sections
        for ch in data:
            chap = str(ch["Chapter"])
            src_chap = chap  # the source's own locator, used for witness.path
            entries, skips = [], []
            for sec in ch["Sections"]:
                s = str(sec["Section"])
                text = norm_ws(sec["Content"])
                if slug == "dort":
                    # Creeds.json labels the Canons' blocks "1", "2", "3&4", "4";
                    # the last block is the Fifth Head (Perseverance of the Saints).
                    # Display label and id say Head 5; witness.path keeps "#4".
                    if src_chap == "4" and "Perseverance" in str(ch.get("Title", "")):
                        chap = "5"
                    heads = "Heads %s" % chap.replace("&", " & ") if "&" in chap else "Head %s" % chap
                    kind = "Art." if s.startswith("A") else "Rejection"
                    ref = "%s, %s, %s %s" % (title, heads, kind, s[1:])
                    eid = "cat-%s-h%s-%s%02d" % (slug, chap.replace("&", ""), s[0].lower(), int(s[1:]))
                else:
                    ref = "%s, %s.%s" % (title, chap, s)
                    eid = "cat-%s-%03d-%03d" % (slug, int(chap), int(s))
                if len(text) > MAX_CHARS:
                    skips.append((ref, len(text)))
                    continue
                entries.append(make_entry(eid, ref, text, title, witness("%s.%s" % (src_chap, s))))
            yield chap, entries, skips
    elif fmt == "Canon":  # flat articles
        for art in data:
            a = str(art["Article"])
            text = norm_ws(art["Content"])
            ref = "%s, Art. %s" % (title, a)
            if len(text) > MAX_CHARS:
                yield a, [], [(ref, len(text))]
                continue
            yield a, [make_entry("cat-%s-%03d" % (slug, int(a)), ref, text, title, witness(a))], []
    else:
        raise SystemExit("unhandled CreedFormat %r in %s" % (fmt, stem))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=int, default=700, help="stop filling once this many entries exist")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("-v", "--verbose", action="store_true", help="list every skipped item")
    args = ap.parse_args()

    if not os.path.isdir(SRC_DIR):
        sys.exit("missing %s; clone https://github.com/NonlinearFruit/Creeds.json into sources/" % SRC_DIR)

    entries, per_doc, skips = [], [], {}
    seen_ids = set()

    def add(doc_title, new, sk):
        for e in new:
            if e["id"] in seen_ids:
                sys.exit("duplicate id %s" % e["id"])
            seen_ids.add(e["id"])
            entries.append(e)
        skips.setdefault(doc_title, []).extend(sk)

    for stem, slug, title in CORE + FILL:
        is_fill = (stem, slug, title) in FILL
        if is_fill and len(entries) >= args.target:
            per_doc.append((title, 0, "not needed (target reached)"))
            continue
        doc = load_doc(stem)
        if doc is None:
            per_doc.append((title, 0, "file missing"))
            continue
        ok, why = eligible(stem, doc)
        if not ok:
            per_doc.append((title, 0, "skipped: " + why))
            continue
        before = len(entries)
        for _unit, new, sk in units_for(stem, slug, title, doc):
            if is_fill and len(entries) >= args.target:
                break
            add(title, new, sk)
        per_doc.append((title, len(entries) - before, "fill" if is_fill else "core"))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("wrote %d creed entries -> %s" % (len(entries), os.path.relpath(args.out, ROOT)))
    print("\n%-36s %5s  %s" % ("document", "count", "role"))
    for title, n, role in per_doc:
        print("%-36s %5d  %s" % (title, n, role))
    total_skips = sum(len(v) for v in skips.values())
    print("\nskipped (> %d chars): %d" % (MAX_CHARS, total_skips))
    for title, items in skips.items():
        if not items:
            continue
        print("  %s: %d" % (title, len(items)))
        for ref, n in (items if args.verbose else items[:5]):
            print("    - %s (%d chars)" % (ref, n))
        if not args.verbose and len(items) > 5:
            print("    ... %d more (-v to list)" % (len(items) - 5))
    print("\nnot in Creeds.json (plan wanted them): " + ", ".join(WANTED_BUT_ABSENT))


if __name__ == "__main__":
    main()
