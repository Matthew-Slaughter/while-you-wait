#!/usr/bin/env python3
"""index-witnesses.py: build sources/index.json, a map from Scripture reference
to candidate witness passages drawn from the open-source clones in sources/.

    "1 Corinthians 10:4": [
      {"voice": "John Chrysostom", "work": "Homilies on 1 Corinthians",
       "source": "HistoricalChristianFaith/Commentaries-Database",
       "path": "John Chrysostom/1 Corinthians 10_1-5.toml",
       "excerpt": "...first 600 chars...", "chars": 4210,
       "granularity": "verse", "range": "1 Corinthians 10:1-5"},
      ...
    ]

Keys are corpus-style single-verse refs ("Psalm 23:1", "Song of Solomon 2:4")
or, for chapter-level material, "<Book> <Chapter>". `path` is relative to the
clone of `source` (repo sources) or to sources/ itself (ccel/calvin). Ranges in a source are
expanded so every verse in the range gets the candidate; `range` records the
span the source actually covers and `granularity` is one of
  "verse"   - the source comments on exactly this verse
  "range"   - the source comments on a span of verses that includes this one
  "chapter" - chapter-level material (keyed "<Book> <Chapter>")

Sources indexed (all public domain; see docs/SOURCES.md):
  Commentaries-Database   verse-keyed TOML, one or more [[commentary]] tables
  chspurgeon-tod          Treasury of David, markdown per Psalm
  matthew-henry-commentary  markdown per chapter, "### Verses a-b" sections
  ccel/calvin             Calvin's Commentaries, CCEL plain text, verse headers

Usage:
  python3 scripts/index-witnesses.py [--corpus plugins/while-you-wait/data/devotionals.json]
                                     [--out sources/index.json] [--excerpt 600]
"""
import argparse
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, "sources")
DEFAULT_CORPUS = os.path.join(ROOT, "plugins", "while-you-wait", "data", "devotionals.json")
DEFAULT_OUT = os.path.join(SOURCES, "index.json")

# ---------------------------------------------------------------------------
# Authors in Commentaries-Database whose works are NOT public domain (or not
# reliably so) and must never be offered as witnesses. Everything by a writer
# who died after 1929, or whose English text is a modern translation still
# under copyright, belongs here. Names are the repo's directory names.
# JB Lightfoot (d. 1889), Wesley, Calvin, Luther, the Fathers etc. are fine.
EXCLUDED_AUTHORS = {
    "CS Lewis",          # d. 1963
    "JRR Tolkien",       # d. 1973
    "GK Chesterton",     # d. 1936; post-1929 works still in copyright
    "Douglas Wilson",    # living
}
# Any author whose metadata.toml default_year is later than this is excluded
# too (catches modern writers added to the repo after this list was written).
# The repo uses default_year=9999 for undatable Pseudo-* authors; those are
# ancient and stay in.
MAX_DEFAULT_YEAR = 1900
UNKNOWN_YEAR = 9999

# ---------------------------------------------------------------------------
BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalm", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
    "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
]
BOOK_SET = set(BOOKS)
ALIASES = {
    "psalms": "Psalm", "psalm": "Psalm", "song of songs": "Song of Solomon", "canticles": "Song of Solomon",
    "songs": "Song of Solomon", "song of solomon": "Song of Solomon", "revelations": "Revelation",
    "1st chronicles": "1 Chronicles", "2nd chronicles": "2 Chronicles", "1st samuel": "1 Samuel",
    "2nd samuel": "2 Samuel", "1st kings": "1 Kings", "2nd kings": "2 Kings",
}
for _b in BOOKS:
    ALIASES[_b.lower()] = _b
    ALIASES[_b.lower().replace(" ", "-")] = _b


def norm_book(name):
    key = re.sub(r"\s+", " ", name.strip()).lower()
    if key in ALIASES:
        return ALIASES[key]
    key2 = re.sub(r"^(i|ii|iii)\b", lambda m: str(len(m.group(1))), key)
    return ALIASES.get(key2)


_WS = re.compile(r"\s+")


def excerpt_of(text, n):
    t = re.sub(r"\\([\\'\"*_\[\]()`])", r"\1", text)  # pandoc escapes in the Henry clone
    t = _WS.sub(" ", t).strip()
    return t[:n]


class Index:
    def __init__(self, excerpt_len):
        self.refs = {}
        self.excerpt_len = excerpt_len
        self.counts = {}

    def add(self, key, cand, source_label):
        self.refs.setdefault(key, []).append(cand)
        self.counts[source_label] = self.counts.get(source_label, 0) + 1

    def add_range(self, book, chapter, v1, v2, text, voice, work, source, path, label):
        if v2 < v1:
            v1, v2 = v2, v1
        span = "%s %d:%d" % (book, chapter, v1) + ("-%d" % v2 if v2 != v1 else "")
        base = {
            "voice": voice, "work": work, "source": source, "path": path,
            "excerpt": excerpt_of(text, self.excerpt_len), "chars": len(text),
            "granularity": "verse" if v1 == v2 else "range", "range": span,
        }
        for v in range(v1, v2 + 1):
            self.add("%s %d:%d" % (book, chapter, v), base, label)

    def add_chapter(self, book, chapter, text, voice, work, source, path, label):
        cand = {
            "voice": voice, "work": work, "source": source, "path": path,
            "excerpt": excerpt_of(text, self.excerpt_len), "chars": len(text),
            "granularity": "chapter", "range": "%s %d" % (book, chapter),
        }
        self.add("%s %d" % (book, chapter), cand, label)


# ---------------------------------------------------------------------------
# Commentaries-Database (TOML subset parser; Python 3.9 has no tomllib)

def parse_toml_subset(raw):
    """Parse the Commentaries-Database TOML shape into a list of dicts.

    Supports [[commentary]] tables, key = '''multi-line''' / \"\"\"...\"\"\" /
    "..." / '...' / bare numbers. Anything else is ignored. Never raises.
    """
    tables, cur = [], None
    i, n = 0, len(raw)
    key_re = re.compile(r"[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*")
    while i < n:
        # skip whitespace / comments
        m = re.compile(r"[ \t\r\n]*(#[^\n]*\n[ \t\r\n]*)*").match(raw, i)
        i = m.end()
        if i >= n:
            break
        if raw.startswith("[[", i):
            j = raw.find("]]", i)
            name = raw[i + 2:j].strip()
            cur = {}
            tables.append((name, cur))
            i = j + 2
            continue
        if raw.startswith("[", i):
            j = raw.find("]", i)
            cur = {}
            tables.append((raw[i + 1:j].strip(), cur))
            i = j + 1
            continue
        m = key_re.match(raw, i)
        if not m:
            i = raw.find("\n", i)
            if i == -1:
                break
            continue
        key = m.group(1)
        i = m.end()
        if raw.startswith("'''", i):
            j = raw.find("'''", i + 3)
            val = raw[i + 3:j] if j != -1 else raw[i + 3:]
            i = j + 3 if j != -1 else n
            if val.startswith("\n"):
                val = val[1:]
        elif raw.startswith('"""', i):
            j = raw.find('"""', i + 3)
            val = raw[i + 3:j] if j != -1 else raw[i + 3:]
            i = j + 3 if j != -1 else n
            val = val.replace('\\"', '"').replace("\\n", "\n")
            if val.startswith("\n"):
                val = val[1:]
        elif raw.startswith('"', i):
            j = i + 1
            while j < n and raw[j] != '"':
                j += 2 if raw[j] == "\\" else 1
            val = raw[i + 1:j].replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
            i = j + 1
        elif raw.startswith("'", i):
            j = raw.find("'", i + 1)
            val = raw[i + 1:j] if j != -1 else raw[i + 1:]
            i = j + 1 if j != -1 else n
        else:
            j = raw.find("\n", i)
            if j == -1:
                j = n
            val = raw[i:j].strip()
            i = j
        if cur is None:
            cur = {}
            tables.append(("", cur))
        cur[key] = val
    return tables


CDB_NAME = re.compile(r"^(.+?) (\d+)_(\d+)(?:-(\d+)(?:_(\d+))?)?\.toml$")


def index_commentaries(ix, stats):
    base = os.path.join(SOURCES, "Commentaries-Database")
    if not os.path.isdir(base):
        print("skip: sources/Commentaries-Database not found")
        return
    label = "HistoricalChristianFaith/Commentaries-Database"
    authors = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)) and not d.startswith("."))
    excluded, files = [], 0
    for author in authors:
        adir = os.path.join(base, author)
        meta = {}
        mpath = os.path.join(adir, "metadata.toml")
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8", errors="replace") as f:
                for _, t in parse_toml_subset(f.read()):
                    meta.update(t)
        year = meta.get("default_year")
        try:
            year = int(str(year).strip()) if year is not None else None
        except ValueError:
            year = None
        if author in EXCLUDED_AUTHORS or (year is not None and year != UNKNOWN_YEAR and year > MAX_DEFAULT_YEAR):
            excluded.append("%s (%s)" % (author, year if year else "listed"))
            continue
        if norm_book(author):
            # Directories named after Bible books hold Scripture quoting
            # Scripture (e.g. Acts/1 Samuel 13_14.toml = Acts 13 citing
            # 1 Samuel). Useful cross-references, but not a witness voice.
            continue
        for fn in os.listdir(adir):
            m = CDB_NAME.match(fn)
            if not m:
                continue
            book = norm_book(m.group(1))
            if not book:
                continue  # apocrypha etc.
            ch1, v1 = int(m.group(2)), int(m.group(3))
            if m.group(5):          # chapter_verse-chapter_verse
                ch2, v2 = int(m.group(4)), int(m.group(5))
            elif m.group(4):        # chapter_verse-verse
                ch2, v2 = ch1, int(m.group(4))
            else:
                ch2, v2 = ch1, v1
            path = os.path.join(adir, fn)
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
            files += 1
            rel = os.path.relpath(path, base)
            for name, t in parse_toml_subset(raw):
                q = t.get("quote", "").strip()
                if not q:
                    continue
                voice = author + (" " + t["append_to_author_name"].strip() if t.get("append_to_author_name") else "")
                work = (t.get("source_title") or "").strip() or "Commentary"
                if ch1 == ch2:
                    ix.add_range(book, ch1, v1, v2, q, voice, work, label, rel, label)
                else:
                    # cross-chapter span: attach to the verses actually named at
                    # both ends; the middle is unknowable without a versification table
                    ix.add_range(book, ch1, v1, v1, q, voice, work, label, rel, label)
                    ix.add_range(book, ch2, v2, v2, q, voice, work, label, rel, label)
    stats["Commentaries-Database"] = {"files": files, "authors_excluded": excluded}


# ---------------------------------------------------------------------------
# Treasury of David

TOD_H3 = re.compile(r"^###\s+Verses?\s+(\d+)(?:\s*(?:-|&|to|,)\s*(\d+))?\s*$")
TOD_119 = re.compile(r"^##\s+Exposition\s+Verses?\s+(\d+)(?:\s*(?:-|&)\s*(\d+))?\s*$")
TOD_NOTE = re.compile(r"^\*\*Verses?\s+(\d+)(?:\s*(?:-|&|,)\s*(\d+))?\s*&mdash;\*\*\s*(.*)$")
TOD_ATTR = re.compile(r"&mdash;\s*\*([^*]+)\*\s*$")


def _tod_sections(lines, psalm, ix, rel, label):
    """Exposition sections; returns nothing, adds candidates."""
    cur = None
    buf = []

    def flush():
        if cur and buf:
            text = "\n".join(buf).strip()
            if text:
                ix.add_range("Psalm", psalm, cur[0], cur[1], text, "Charles H. Spurgeon",
                             "The Treasury of David", "lyteword/chspurgeon-tod", rel, label)

    in_expo = False
    for line in lines:
        if line.startswith("## "):
            m = TOD_119.match(line)
            if m:
                flush()
                cur = (int(m.group(1)), int(m.group(2) or m.group(1)))
                buf = []
                in_expo = True
                continue
            in_expo = line.strip() == "## Exposition"
            flush()
            cur, buf = None, []
            continue
        if line.startswith("### "):
            m = TOD_H3.match(line)
            if m and in_expo:
                flush()
                cur = (int(m.group(1)), int(m.group(2) or m.group(1)))
                buf = []
            else:
                flush()
                cur, buf = None, []
            continue
        if cur is not None:
            if line.startswith(">"):
                continue  # quoted verse text
            buf.append(line)
    flush()


def _tod_notes(lines, psalm, ix, rel, label):
    for line in lines:
        m = TOD_NOTE.match(line.strip())
        if not m:
            continue
        v1, v2 = int(m.group(1)), int(m.group(2) or m.group(1))
        body = m.group(3).strip()
        a = TOD_ATTR.search(body)
        if not a:
            continue
        who = re.sub(r"[,;]?\s*\(?\b(c\.|circa|d\.)?\s*\d{3,4}(\s*[-–]\s*\d{3,4})?\)?\.?\s*$", "", a.group(1)).strip(" .,")
        text = body[:a.start()].strip()
        if not who or len(text) < 40:
            continue
        ix.add_range("Psalm", psalm, v1, v2, text, who,
                     "quoted in Spurgeon's Treasury of David", "lyteword/chspurgeon-tod", rel, label)


def index_treasury(ix, stats):
    base = os.path.join(SOURCES, "chspurgeon-tod")
    if not os.path.isdir(base):
        print("skip: sources/chspurgeon-tod not found")
        return
    label = "lyteword/chspurgeon-tod"
    files = 0
    paths = glob.glob(os.path.join(base, "volume-*", "psalm-*.md")) + \
        glob.glob(os.path.join(base, "volume-*", "psalm-*", "verses-*.md"))
    for path in sorted(paths):
        m = re.search(r"psalm-(\d+)", path)
        psalm = int(m.group(1))
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        rel = os.path.relpath(path, base)
        files += 1
        _tod_sections(lines, psalm, ix, rel, label)
        _tod_notes(lines, psalm, ix, rel, label)
    stats["chspurgeon-tod"] = {"files": files}


# ---------------------------------------------------------------------------
# Matthew Henry

MHC_FILE = re.compile(r"^MHC - (.+?)(?:, Chapter| )\s*(\d+)\.md$")
MHC_H3 = re.compile(r"^###\s+Verses?\s+(\d+)[ab]?(?:\s*-\s*(\d+)[ab]?)?\s*$")


def index_henry(ix, stats):
    base = os.path.join(SOURCES, "matthew-henry-commentary")
    if not os.path.isdir(base):
        print("skip: sources/matthew-henry-commentary not found")
        return
    label = "revisedcommonversion/matthew-henry-commentary"
    files, chapters = 0, 0
    for d in sorted(os.listdir(base)):
        ddir = os.path.join(base, d)
        if not os.path.isdir(ddir) or d.startswith("."):
            continue
        book = norm_book(d)
        if not book:
            continue
        for fn in sorted(os.listdir(ddir)):
            m = MHC_FILE.match(fn)
            if not m:
                continue
            chapter = int(m.group(2))
            path = os.path.join(ddir, fn)
            rel = os.path.relpath(path, base)
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            files += 1
            intro, cur, buf = [], None, []

            def flush():
                if cur and buf:
                    text = "\n".join(buf).strip()
                    if text:
                        ix.add_range(book, chapter, cur[0], cur[1], text, "Matthew Henry",
                                     "Commentary on the Whole Bible", label, rel, label)

            prev = ""
            for line in lines:
                h = MHC_H3.match(line)
                if h:
                    flush()
                    cur = (int(h.group(1)), int(h.group(2) or h.group(1)))
                    buf = []
                    continue
                if line.startswith("#"):
                    continue
                if re.match(r"^(=+|-+)\s*$", line):
                    # setext underline: drop it and the heading line above
                    if cur is None and intro and intro[-1] == prev:
                        intro.pop()
                    prev = line
                    continue
                prev = line
                if cur is None:
                    intro.append(line)
                else:
                    buf.append(line)
            flush()
            intro_text = "\n".join(intro).strip()
            if len(intro_text) > 200:
                chapters += 1
                ix.add_chapter(book, chapter, intro_text, "Matthew Henry", "Commentary on the Whole Bible",
                               label, rel, label)
    stats["matthew-henry-commentary"] = {"files": files, "chapter_intros": chapters}


# ---------------------------------------------------------------------------
# Calvin (CCEL plain text)

CAL_TITLE = re.compile(r"^\s*Title:\s*Commentar(?:y|ies) on (?:the )?(.+?)(?: - Volume \d+)?\s*$", re.M)


def index_calvin(ix, stats):
    base = os.path.join(SOURCES, "ccel", "calvin")
    if not os.path.isdir(base):
        print("skip: sources/ccel/calvin not found")
        return
    label = "ccel.org/ccel/calvin"
    files, sections = 0, 0
    for path in sorted(glob.glob(os.path.join(base, "calcom*.txt"))):
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        t = CAL_TITLE.search(raw)
        if not t:
            continue
        book = norm_book(t.group(1).replace("Epistle to the ", "").replace("Gospel according to ", ""))
        if not book:
            print("calvin: unknown book in", path, t.group(1))
            continue
        rel = os.path.relpath(path, SOURCES)
        files += 1
        work = "Commentary on %s" % ("the Psalms" if book == "Psalm" else book)
        hdr = re.compile(r"^\s{1,6}%s (\d+):(\d+)(?:-(\d+))?\s*$" % re.escape(book), re.M)
        heads = list(hdr.finditer(raw))
        for k, h in enumerate(heads):
            start = h.end()
            end = heads[k + 1].start() if k + 1 < len(heads) else len(raw)
            body = raw[start:end]
            # drop the next-chapter banner and footnote block tails
            body = re.split(r"\n\s*CHAPTER \d+\s*\n", body)[0]
            ch, v1 = int(h.group(1)), int(h.group(2))
            v2 = int(h.group(3)) if h.group(3) else v1
            sections += 1
            # per-verse split: the *last* paragraph leader "N. " for each verse
            # starts Calvin's comment on it (earlier leaders are the verse text
            # and its Latin rendering).
            leaders = [(m.start(), int(m.group(1))) for m in re.finditer(r"(?m)^\s{1,6}(\d+)\.\s+\S", body)]
            last = {}
            for pos, num in leaders:
                if v1 <= num <= v2:
                    last[num] = pos
            per_verse = {}
            if last:
                starts = sorted(last.items(), key=lambda kv: kv[1])
                for j, (num, pos) in enumerate(starts):
                    nxt = starts[j + 1][1] if j + 1 < len(starts) else len(body)
                    seg = body[pos:nxt].strip()
                    if len(seg) > 200:
                        per_verse[num] = seg
            if per_verse:
                for num, seg in per_verse.items():
                    ix.add_range(book, ch, num, num, seg, "John Calvin", work, label, rel, label)
                missing = [v for v in range(v1, v2 + 1) if v not in per_verse]
                if missing:
                    for v in missing:
                        ix.add_range(book, ch, v, v, body.strip(), "John Calvin", work, label, rel, label)
                        ix.refs["%s %d:%d" % (book, ch, v)][-1]["granularity"] = "range"
                        ix.refs["%s %d:%d" % (book, ch, v)][-1]["range"] = "%s %d:%d-%d" % (book, ch, v1, v2)
            else:
                ix.add_range(book, ch, v1, v2, body.strip(), "John Calvin", work, label, rel, label)
    stats["ccel/calvin"] = {"files": files, "sections": sections}


# ---------------------------------------------------------------------------

REF_RE = re.compile(r"^(.+?) (\d+):(\d+)(?:-(\d+))?$")


def coverage(ix, corpus_path):
    with open(corpus_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["entries"] if isinstance(data, dict) and "entries" in data else data
    refs = [e["ref"] for e in entries if e.get("kind") == "scripture"]
    covered_any, covered_all, uncovered = 0, 0, []
    for ref in refs:
        m = REF_RE.match(ref)
        if not m:
            uncovered.append(ref)
            continue
        book = norm_book(m.group(1))
        ch, v1 = int(m.group(2)), int(m.group(3))
        v2 = int(m.group(4)) if m.group(4) else v1
        hits = ["%s %d:%d" % (book, ch, v) in ix.refs for v in range(v1, v2 + 1)]
        if any(hits):
            covered_any += 1
        if all(hits):
            covered_all += 1
        if not any(hits):
            uncovered.append(ref)
    books_seen = set()
    for key in ix.refs:
        m = REF_RE.match(key) or re.match(r"^(.+?) (\d+)$", key)
        if m:
            books_seen.add(m.group(1))
    zero_books = [b for b in BOOKS if b not in books_seen]
    return len(refs), covered_any, covered_all, uncovered, zero_books


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--excerpt", type=int, default=600)
    args = ap.parse_args()

    t0 = time.time()
    ix = Index(args.excerpt)
    stats = {}
    index_commentaries(ix, stats)
    index_treasury(ix, stats)
    index_henry(ix, stats)
    index_calvin(ix, stats)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(ix.refs, f, ensure_ascii=False)
    size = os.path.getsize(args.out)

    print("index-witnesses: %d keys, %d candidates -> %s (%.1f MB, %.0fs)" % (
        len(ix.refs), sum(len(v) for v in ix.refs.values()), os.path.relpath(args.out, ROOT), size / 1e6, time.time() - t0))
    print("\ncandidates per source:")
    for k, v in sorted(ix.counts.items(), key=lambda kv: -kv[1]):
        print("  %-55s %8d" % (k, v))
    for k, v in stats.items():
        print("  %s: %s" % (k, json.dumps({kk: (vv if not isinstance(vv, list) else len(vv)) for kk, vv in v.items()})))
    exc = stats.get("Commentaries-Database", {}).get("authors_excluded", [])
    if exc:
        print("  excluded Commentaries-Database authors: " + ", ".join(exc))

    if os.path.exists(args.corpus):
        total, any_, all_, unc, zero = coverage(ix, args.corpus)
        print("\ncorpus coverage: %d scripture refs; %d have >=1 candidate on some verse (%d on every verse); %d uncovered"
              % (total, any_, all_, len(unc)))
        if unc:
            print("  uncovered: " + ", ".join(unc))
        print("books (of 66) with zero coverage: %s" % (", ".join(zero) if zero else "none"))
    else:
        print("corpus not found at %s; skipping coverage" % args.corpus)


if __name__ == "__main__":
    main()
