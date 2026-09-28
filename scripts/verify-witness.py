#!/usr/bin/env python3
"""verify-witness.py: prove every `witness` in a corpus points at real text.

For each entry that carries a `witness` object:

  * open  sources/<witness.path>  (the repo slug in witness.source is
    informational; the path already starts with the clone directory name);
  * extract the text of that file: TOML `quote` fields
    (Commentaries-Database), JSON string values (Creeds.json), abc `W:`/`w:`
    lyric lines (openhymnal), or the raw markdown/plain text otherwise;
  * normalize both sides (whitespace collapsed, curly quotes and dashes
    unified, casefolded) and require witness.quote to be a substring of the
    source text AND of the entry's insight.

Entries whose witness.quote is "" (mechanically ingested creeds and hymns
that still await the humanize pass) are checked differently: the entry's
own `text` must be a substring of the source file, which proves the primary
text is verbatim.

If the exact normalized substring isn't found, a fuzzy fallback kicks in
before the entry is failed: locate candidate windows in the source using
2-3 distinct word-trigrams drawn from the quote (first, middle, last),
compare each window against the quote with difflib.SequenceMatcher, and
accept the match if ratio >= 0.95. This absorbs archive.org OCR noise
(scanned page headers/numbers spliced mid-sentence, misread letters) without
weakening the guarantee that real, near-verbatim text was found -- a fuzzy
match is reported as "fuzzy (0.97)" alongside the exact-match counts.

Exit 1 with a per-entry report on any failure; exit 0 with counts otherwise.

Usage:
  python3 scripts/verify-witness.py <corpus.json> [--sample N] [--sources DIR]
"""
import argparse
import difflib
import json
import os
import random
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCES = os.path.join(ROOT, "sources")

_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "′": "'", "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "…": "...",
}
_TRANS = str.maketrans(_QUOTES)
_WS = re.compile(r"\s+")
_MD_ENT = {"&mdash;": "-", "&ndash;": "-", "&quot;": '"', "&amp;": "&", "&#39;": "'", "&rsquo;": "'", "&lsquo;": "'", "&ldquo;": '"', "&rdquo;": '"'}


def normalize(s):
    s = unicodedata.normalize("NFKC", s)
    for k, v in _MD_ENT.items():
        s = s.replace(k, v)
    s = s.translate(_TRANS)
    s = re.sub(r"\\([\\'\"*_\[\]()`])", r"\1", s)  # pandoc escapes (Henry clone)
    s = re.sub(r"\[Illustration:[^\]]*\]", " ", s)  # Gutenberg picture markers
    # hymnals print a marginal scripture reference as its own line inside a stanza; it is apparatus, not text
    s = re.sub(r"(?m)^[ \t]*(?:[1-3][ \t]*)?[A-Z][a-z]{1,5}\.?[ \t]*\d+[:.,\d \t-]*[ \t]*$\n?", "", s)
    # OCR / typeset scans break words at line ends: "love-\n liness" -> "loveliness"
    s = re.sub(r"([A-Za-z])-[ \t]*\r?\n[ \t]*([a-z])", r"\1\2", s)
    s = s.replace("\\-", "")  # abc soft hyphen (openhymnal)
    # markup never counts, only the words: markdown/Gutenberg emphasis and code ticks
    s = s.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
    # "- -" (a dash split by normalization) and "--" both read as a dash
    s = re.sub(r"-\s*-+", "-", s)
    s = _WS.sub(" ", s)
    return s.strip().casefold()


# ---------- fuzzy fallback (archive.org OCR noise) -----------------------

FUZZY_THRESHOLD = 0.95
_MAX_HITS_PER_TRIGRAM = 20  # cap: keeps a 9MB djvu.txt well under a second


def _trigrams(words):
    """First, middle, and near-last 3-word runs of a normalized quote."""
    if len(words) < 6:
        return []
    idxs = sorted({0, len(words) // 2, max(0, len(words) - 3)})
    out = []
    for i in idxs:
        tri = " ".join(words[i:i + 3])
        if len(tri) >= 6:
            out.append(tri)
    return list(dict.fromkeys(out))  # de-dup, keep order


def _window_ratio(nq, window):
    """Ratio of nq against the best contiguous run of matching blocks in
    window, so a spliced-in page header/number (a gap in the middle) doesn't
    drag in unrelated trailing text the way a fixed-length slice would."""
    sm = difflib.SequenceMatcher(None, nq, window, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size > 0]
    if not blocks:
        return 0.0
    best_run, cur = [], [blocks[0]]
    for prev, b in zip(blocks, blocks[1:]):
        # small gaps (an OCR-garbled word, a spliced header) stay in the run
        if (b.b - (prev.b + prev.size)) <= 80 and (b.a - (prev.a + prev.size)) <= 20:
            cur.append(b)
        else:
            if sum(x.size for x in cur) > sum(x.size for x in best_run):
                best_run = cur
            cur = [b]
    if sum(x.size for x in cur) > sum(x.size for x in best_run):
        best_run = cur
    start = min(x.b for x in best_run)
    end = max(x.b + x.size for x in best_run)
    return difflib.SequenceMatcher(None, nq, window[start:end], autojunk=False).ratio()


def fuzzy_ratio(nq, src, threshold=FUZZY_THRESHOLD):
    """Best fuzzy-match ratio for normalized quote `nq` inside normalized
    source `src`, or None if no candidate window reaches `threshold`.

    Anchors on 2-3 word-trigrams from the quote (a single OCR-garbled word
    rarely corrupts all three), then scores a window around each hit."""
    words = nq.split()
    trigrams = _trigrams(words)
    if not trigrams:
        return None
    qlen = len(nq)
    best = 0.0
    for tri in trigrams:
        start = 0
        for _ in range(_MAX_HITS_PER_TRIGRAM):
            pos = src.find(tri, start)
            if pos == -1:
                break
            start = pos + 1
            window = src[max(0, pos - qlen):pos + qlen + 120]
            r = _window_ratio(nq, window)
            if r > best:
                best = r
                if best >= threshold:
                    return best
    return best if best >= threshold else None


def matches(nq, src, threshold=FUZZY_THRESHOLD):
    """(ok, label) -- exact substring first, then the fuzzy fallback."""
    if not nq:
        return True, "exact"
    if nq in src:
        return True, "exact"
    r = fuzzy_ratio(nq, src, threshold)
    if r is not None:
        return True, "fuzzy (%.2f)" % r
    return False, None


# ---------- source extractors -------------------------------------------

def _toml_quotes(raw):
    """Return the concatenated `quote` values of every [[commentary]] table.

    Handles the subset used by Commentaries-Database: quote = '''...''' /
    quote = \"\"\"...\"\"\" / quote = \"...\" / quote = '...'.
    """
    out = []
    i = 0
    n = len(raw)
    pat = re.compile(r"^\s*quote\s*=\s*", re.M)
    while True:
        m = pat.search(raw, i)
        if not m:
            break
        j = m.end()
        if raw.startswith("'''", j):
            k = raw.find("'''", j + 3)
            out.append(raw[j + 3:k] if k != -1 else raw[j + 3:])
            i = k + 3 if k != -1 else n
        elif raw.startswith('"""', j):
            k = raw.find('"""', j + 3)
            body = raw[j + 3:k] if k != -1 else raw[j + 3:]
            out.append(_unescape_basic(body))
            i = k + 3 if k != -1 else n
        elif raw.startswith('"', j):
            k = j + 1
            while k < n and raw[k] != '"':
                k += 2 if raw[k] == "\\" else 1
            out.append(_unescape_basic(raw[j + 1:k]))
            i = k + 1
        elif raw.startswith("'", j):
            k = raw.find("'", j + 1)
            out.append(raw[j + 1:k] if k != -1 else raw[j + 1:])
            i = k + 1 if k != -1 else n
        else:
            i = j
    return "\n".join(out)


def _unescape_basic(s):
    return (s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
             .replace("\\\\", "\\"))


def _json_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _json_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _json_strings(v, out)
    return out


def _abc_lyrics(raw):
    """Lyric text of an ABC file.

    `W:` lines are plain stanzas. `w:` lines are syllables aligned under the
    notes and, when a tune carries several stanzas, are interleaved: each
    musical phrase is followed by one `w:` line per stanza (stanza numbers
    like "1.~" mark the first phrase). We rebuild each stanza by joining its
    line from every phrase block, re-join hyphenated syllables, and drop the
    alignment marks (~ * _)."""
    def clean(t):
        t = re.sub(r"^\s*\d+\.", " ", t)
        t = t.replace("~", " ").replace("*", " ").replace("_", " ")
        return re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", t)

    out, blocks, cur = [], [], []
    for line in raw.splitlines():
        if line.startswith("W:"):
            out.append(clean(line[2:]))
        elif line.startswith("w:"):
            cur.append(clean(line[2:]))
        else:
            if cur:
                blocks.append(cur); cur = []
    if cur:
        blocks.append(cur)
    if blocks:
        n = max(len(b) for b in blocks)
        for k in range(n):                      # stanza k = its line from each phrase block
            out.append(" ".join(b[k] for b in blocks if k < len(b)))
        for b in blocks:                        # and the raw lines, for single-stanza files
            out.extend(b)
    return "\n".join(out)

def _strip_html(raw):
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return raw


def extract_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".toml":
        return _toml_quotes(raw)
    if ext == ".json":
        try:
            return "\n".join(_json_strings(json.loads(raw), []))
        except ValueError:
            return raw
    if ext == ".abc":
        return _abc_lyrics(raw)
    if ext in (".html", ".htm", ".xml", ".thml"):
        return _strip_html(raw)
    return raw


_CACHE = {}


_WEB_EXTS = (".txt", ".html", ".htm", ".json", ".xml", ".thml", ".md")
_CT_EXT = {
    "application/json": ".json", "text/json": ".json",
    "text/html": ".html", "application/xhtml+xml": ".html",
    "text/plain": ".txt", "text/markdown": ".md",
    "text/xml": ".xml", "application/xml": ".xml",
}


def _web_cache_key(url):
    import hashlib
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _web_cache_path(sources_dir, url, content_type=None):
    """Cache file for a URL witness: sources/web/<sha1[:16]>.<ext>.

    The extension decides which extractor runs, so at fetch time it is taken
    from the response Content-Type (application/json -> .json, text/html ->
    .html, text/plain -> .txt, ...); an API query URL ending in
    "?q=...&size=1" says nothing useful about its body. Without a
    Content-Type (or an unknown one) fall back to guessing from the URL."""
    h = _web_cache_key(url)
    ext = None
    if content_type:
        ext = _CT_EXT.get(content_type.split(";", 1)[0].strip().lower())
    if ext is None:
        tail = url.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        ext = os.path.splitext(tail)[1].lower()
        if ext not in _WEB_EXTS:
            ext = ".html" if (ext in ("", ".php") or "hymnary.org" in url or "wiki" in url) else ".txt"
    return os.path.join(sources_dir, "web", h + ext)


def _web_cache_find(sources_dir, url):
    """An already-cached copy of url under any extension, or None."""
    h = _web_cache_key(url)
    for ext in _WEB_EXTS:
        c = os.path.join(sources_dir, "web", h + ext)
        if os.path.isfile(c):
            return c
    return None


_REDIRECT_CODES = (301, 302, 303, 307, 308)


def _fetch(url, dest=None, max_redirects=5):
    """GET url, following redirects by hand; returns (bytes, content_type).
    With dest, the body is also written there atomically.

    urllib's HTTPRedirectHandler already follows 301/302/303/307, but (on the
    Python versions this repo targets) has no handler for 308 Permanent
    Redirect, so a 308 surfaces as an HTTPError instead of being followed.
    spurgeon.org serves exactly that, so read the Location header ourselves
    for any 3xx and hop, capped at max_redirects."""
    import urllib.error
    import urllib.parse
    import urllib.request
    headers = {"User-Agent": "while-you-wait verify-witness (+https://github.com/Matthew-Slaughter/while-you-wait)"}
    content_type = None
    for _ in range(max_redirects + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                content_type = r.headers.get("Content-Type")
            break
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECT_CODES:
                location = exc.headers.get("Location")
                if not location:
                    raise
                url = urllib.parse.urljoin(url, location)
                continue
            raise
    else:
        raise RuntimeError("too many redirects for %s" % url)
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
    return data, content_type


def resolve(sources_dir, source, rel, fetch=False):
    """witness.path is relative to the clone of witness.source (plan
    convention, e.g. "John Chrysostom/1 Corinthians 10_1-5.toml" under
    HistoricalChristianFaith/Commentaries-Database), or, for non-repo
    downloads, relative to sources/ itself. Try both, plus the literal
    sources/<source>/<path>.

    When witness.source is an http(s) URL the document is cached under
    sources/web/<sha1>.<ext> (ext from the response Content-Type); with
    fetch=True a missing cache entry is downloaded once. This makes URL witnesses reproducible by anyone."""
    cands = [
        os.path.join(sources_dir, rel),
        os.path.join(sources_dir, os.path.basename(source.rstrip("/")), rel),
        os.path.join(sources_dir, source, rel),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    if source.startswith(("http://", "https://")):
        cached = _web_cache_find(sources_dir, source)
        if cached:
            return cached
        if fetch:
            try:
                data, content_type = _fetch(source)
                cached = _web_cache_path(sources_dir, source, content_type)
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                tmp = cached + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, cached)
                return cached
            except Exception as exc:  # network failure -> reported as not found
                sys.stderr.write("fetch failed for %s: %s\n" % (source, exc))
    return None


def source_text(path):
    if path not in _CACHE:
        _CACHE[path] = normalize(extract_text(path))
    return _CACHE[path]


# ---------- main ---------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("--sample", type=int, default=0, help="print N random verified witness lines")
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--fetch", action="store_true", help="download URL-sourced witnesses into sources/web/ when missing")
    args = ap.parse_args()

    with open(args.corpus, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["entries"] if isinstance(data, dict) and "entries" in data else data

    failures, verified, blank_ok, without = [], [], 0, 0
    exact_ct, fuzzy_ct, fuzzy_notes = 0, 0, []
    for idx, e in enumerate(entries):
        w = e.get("witness")
        if not w:
            without += 1
            continue
        label = e.get("id") or "%s #%d" % (e.get("ref", "?"), idx)
        problems = []
        for key in ("voice", "work", "source", "path"):
            if not w.get(key):
                problems.append("witness.%s missing" % key)
        rel = (w.get("path") or "").split("#", 1)[0]
        full = resolve(args.sources, w.get("source") or "", rel, fetch=args.fetch)
        if rel and not full:
            problems.append("source file not found under sources/ for %s :: %s" % (w.get("source"), rel))
        if problems:
            failures.append((label, problems))
            continue
        src = source_text(full)
        shown = "sources/" + os.path.relpath(full, args.sources)
        quote = w.get("quote") or ""
        if quote.strip():
            nq = normalize(quote)
            ok, label_kind = matches(nq, src)
            if not ok:
                problems.append("witness.quote not found in %s" % shown)
            elif label_kind == "exact":
                exact_ct += 1
            else:
                fuzzy_ct += 1
                fuzzy_notes.append("%s %s" % (label_kind, label))
            # quotes anchor on their own text; everything else on the insight
            anchor_field = "text" if e.get("kind") == "quote" else "insight"
            if nq not in normalize(e.get(anchor_field) or ""):
                problems.append("witness.quote not found in entry %s" % anchor_field)
            if len(quote.split()) > 40:
                problems.append("witness.quote is %d words (> 40)" % len(quote.split()))
        else:
            text = e.get("text") or ""
            # catechism entries are framed "Q. <question> A. <answer>" by the
            # ingester; the question and the answer are each verbatim
            splits = [[text]]
            if e.get("kind") == "creed" and text.startswith("Q. "):
                body = text[3:]
                splits = [[body[:k], body[k + 4:]] for k in range(len(body)) if body.startswith(" A. ", k)] or splits
            # each candidate split's pieces, matched (exact-or-fuzzy) against src
            results = [[matches(normalize(p), src) for p in pieces] for pieces in splits]
            best = min(results, key=lambda res: sum(1 for ok, _ in res if not ok))
            if not text.strip():
                problems.append("witness.quote is blank and entry text is empty")
            elif any(not ok for ok, _ in best):
                problems.append("witness.quote blank and entry text not found verbatim in %s" % shown)
            else:
                blank_ok += 1
                fuzzy_kinds = [k for _, k in best if k != "exact"]
                if fuzzy_kinds:
                    fuzzy_ct += 1
                    fuzzy_notes.append("%s %s" % (fuzzy_kinds[0], label))
                else:
                    exact_ct += 1
        if problems:
            failures.append((label, problems))
        else:
            verified.append(e)

    if failures:
        print("verify-witness: %d failure(s)" % len(failures))
        for label, probs in failures:
            print("  %s" % label)
            for p in probs:
                print("    - %s" % p)
        print("verified %d, failed %d, entries without witness %d" % (len(verified), len(failures), without))
        sys.exit(1)

    quoted = len(verified) - blank_ok
    if fuzzy_notes:
        for note in fuzzy_notes:
            print("  %s" % note)
    print("verify-witness: OK. %d witnessed entries verified (%d quote lines, %d verbatim primary texts; %d exact, %d fuzzy); %d entries without witness."
          % (len(verified), quoted, blank_ok, exact_ct, fuzzy_ct, without))
    if args.sample:
        pool = [e for e in verified if (e["witness"].get("quote") or "").strip()] or verified
        for e in random.sample(pool, min(args.sample, len(pool))):
            w = e["witness"]
            shown = w.get("quote") or e.get("text", "")
            print("\n[%s] %s\n  %s, %s\n  %s :: %s\n  \"%s\"" % (
                e.get("id", "?"), e.get("ref", ""), w["voice"], w["work"], w["source"], w["path"], shown))


if __name__ == "__main__":
    main()
