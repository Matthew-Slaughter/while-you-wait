#!/usr/bin/env python3
"""Check every `kind: scripture` entry against the published translation.

    python3 scripts/check-scripture.py [--corpus PATH] [--kjv PATH]
                                       [--esv-cache PATH] [--translation KJV|ESV]
                                       [--ids id,id,...] [--json OUT] [--strict] [-v]

Sources
  KJV  a public-domain whole-Bible JSON file (--kjv, or env KJV_JSON). Two
       layouts are auto-detected: scrollmapper/bible_databases
       ({"books":[{"name","chapters":[{"chapter","verses":[{"verse","text"}]}]}]})
       and thiagobodruk/bible ([{"abbrev","chapters":[[verse,...],...]}]).
       Books are matched by canonical order (66 books), not by name. The file
       must keep the small-caps divine name as "LORD" (the scrollmapper JSON
       flattens it to "Lord" and is therefore rejected with a warning; the
       thiagobodruk file has two known quirks, "Beth-lehem" in Micah 5:2 and a
       leaked footnote in Jonah 1:9). A third layout is a flat
       {"Book c:v[-v2]": text} file of verified passages, which is what
       corpus/sources/kjv-verified.json holds (bible-api.com KJV cross-checked
       against the other two); entries whose ref it lacks are UNCHECKED.
  ESV  the Crossway API (https://api.esv.org/v3/passage/text/). Set
       ESV_API_KEY; responses are cached in --esv-cache (default
       corpus/sources/esv-cache.json) so reruns cost nothing. Without a key the
       cache is still consulted and un-cached entries are reported as
       UNCHECKED rather than failing. Hand-verified texts can be placed in the
       cache under the ref string.

Comparison: NFKC, whitespace collapsed, curly quotes/dashes unified, verse
numbers, footnote markers and headings stripped from the source, then
  EXACT       identical after quote-style and trailing-punctuation neutralisation
  PUNCT       same words and case, punctuation differs (e.g. added period)
  CASE        same words, case differs (KJV "LORD" flattened to "Lord")
  PARTIAL     corpus text is a clause-boundary prefix/suffix of the source
              (ok only when the ref carries an a/b suffix)
  WORD-DIFF   different words (truncation, ellipsis, paraphrase)
  UNCHECKED   no source text available
Exit status 1 when any CASE, WORD-DIFF or unlabelled PARTIAL is found;
--strict also fails on PUNCT. Stdlib only.
"""
import argparse, importlib.util, json, os, re, sys, unicodedata, urllib.parse, urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_CORPUS = os.path.join(ROOT, "plugins", "while-you-wait", "data", "devotionals.json")
DEFAULT_ESV_CACHE = os.path.join(ROOT, "corpus", "sources", "esv-cache.json")
DEFAULT_KJV = os.path.join(ROOT, "corpus", "sources", "kjv-verified.json")
ESV_API = "https://api.esv.org/v3/passage/text/"

_spec = importlib.util.spec_from_file_location(
    "validate_corpus", os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate-corpus.py"))
_vc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_vc)
BOOKS, parse_ref = _vc.BOOKS, _vc.parse_ref

# ---------------------------------------------------------------------------
# refs
# ---------------------------------------------------------------------------
_SUFFIX = re.compile(r"^(.*?\d)([ab])$")


def split_ref(ref):
    """Return (parsed tuple, partial-suffix or None) for 'Book c:v[-v2][a|b]'."""
    m = _SUFFIX.match(ref.strip())
    suffix = None
    if m:
        ref, suffix = m.group(1), m.group(2)
    return parse_ref(ref), suffix


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------
# em/en dashes are spaced out so "us—for" (ESV) and "us — for" (corpus style) compare equal
_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "′": "'",
           "–": " — ", "—": " — ", "‒": " — ", " ": " "}
_MARKERS = re.compile(r"\[\d+\]|\(\d+\)|\[[a-z]\]|¹|²|³")


def clean(s):
    s = unicodedata.normalize("NFKC", s or "")
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    s = _MARKERS.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)          # "LORD ." -> "LORD."
    return re.sub(r"\s+", " ", s).strip()


def neutral(s):
    """clean() with quote marks removed (a rendering choice in the corpus: the box wraps
    the text in curly double quotes and inner quotes are re-levelled) and edge
    punctuation stripped. Apostrophes inside words are kept."""
    s = clean(s).replace('"', "")
    s = re.sub(r"(?<!\w)'|'(?!\w)", "", s)
    s = re.sub(r"^[\s(\[]+|[\s.,;:!?)\]]+$", "", s)
    return re.sub(r"\s+", " ", s)


def words(s, fold_case=False):
    s = re.sub(r"[^\w\s'-]", " ", clean(s))
    s = re.sub(r"(?<!\w)'|'(?!\w)", " ", s)          # strip quote marks, keep apostrophes
    if fold_case:
        s = s.lower()
    return s.split()


def classify(corpus_text, source_text, suffix):
    if source_text is None:
        return "UNCHECKED", ""
    if neutral(corpus_text) == neutral(source_text):
        return "EXACT", ""
    cw, sw = words(corpus_text), words(source_text)
    if cw == sw:
        return "PUNCT", ""
    cwl, swl = words(corpus_text, True), words(source_text, True)
    if cwl == swl:
        diffs = sorted({f"{b}->{a}" for a, b in zip(cw, sw) if a != b})
        return "CASE", ", ".join(diffs)
    if "..." in corpus_text or "…" in corpus_text:
        return "WORD-DIFF", "ellipsis"
    n = len(cwl)
    if n and n < len(swl):
        if swl[:n] == cwl:
            return "PARTIAL", f"prefix; source continues '{' '.join(sw[n:n + 8])}...'"
        if swl[-n:] == cwl:
            return "PARTIAL", f"suffix; source begins '{' '.join(sw[:len(sw) - n][:8])}...'"
        for i in range(1, len(swl) - n):
            if swl[i:i + n] == cwl:
                return "PARTIAL", f"middle (from word {i}); source begins '{' '.join(sw[:i][:6])}...'"
    # first/last differing word for the report
    i = 0
    while i < min(len(cwl), len(swl)) and cwl[i] == swl[i]:
        i += 1
    j = 0
    while j < min(len(cwl), len(swl)) - i and cwl[-1 - j] == swl[-1 - j]:
        j += 1
    got = " ".join(cw[i:len(cw) - j]) or "(nothing)"
    want = " ".join(sw[i:len(sw) - j]) or "(nothing)"
    return "WORD-DIFF", f"corpus '{got}' vs source '{want}'"


# ---------------------------------------------------------------------------
# KJV
# ---------------------------------------------------------------------------
def load_kjv(path):
    """Return {(book_index, chapter, verse): text} from either supported layout."""
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    verses = {}
    if isinstance(data, dict) and "books" in data:
        books = data["books"]
        for bi, book in enumerate(books):
            for ch in book["chapters"]:
                for v in ch["verses"]:
                    verses[(bi, int(ch["chapter"]), int(v["verse"]))] = v["text"]
    elif isinstance(data, dict) and all(isinstance(v, str) for v in data.values()):
        # flat {"Book c:v[-v2]": text} of verified passages (corpus/sources/kjv-verified.json)
        flat = {}
        for ref, text in data.items():
            _, code, chapter, v1, v2 = parse_ref(_SUFFIX.sub(r"\1", ref))
            flat[(code, chapter, v1, v2)] = text
        flat["__flat__"] = True
        return flat
    elif isinstance(data, list) and data and "chapters" in data[0]:
        books = data
        for bi, book in enumerate(books):
            for ci, ch in enumerate(book["chapters"], 1):
                for vi, text in enumerate(ch, 1):
                    verses[(bi, ci, vi)] = text
    else:
        sys.exit(f"unrecognised KJV layout in {path}")
    if len(books) != 66:
        sys.exit(f"{path}: expected 66 books, found {len(books)}")
    sample = " ".join(list(verses.values())[:3000])
    if "LORD" not in sample:
        print(f"WARN: {path} has no 'LORD' in Genesis; the divine name is flattened, "
              "CASE checks will be wrong", file=sys.stderr)
    return verses


def kjv_passage(verses, parsed):
    _, code, chapter, v1, v2 = parsed
    if verses.get("__flat__"):
        if (code, chapter, v1, v2) in verses:
            return verses[(code, chapter, v1, v2)]
        parts = [verses.get((code, chapter, v, v)) for v in range(v1, v2 + 1)]
        return " ".join(parts) if all(parts) else None
    bi = next(i for i, b in enumerate(BOOKS) if b[1] == code)
    parts = []
    for v in range(v1, v2 + 1):
        t = verses.get((bi, chapter, v))
        if t is None:
            return None
        parts.append(t)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# ESV
# ---------------------------------------------------------------------------
def load_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path, cache):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    os.replace(tmp, path)


def esv_fetch(ref, key):
    q = urllib.parse.urlencode({
        "q": ref, "include-headings": "false", "include-footnotes": "false",
        "include-verse-numbers": "false", "include-short-copyright": "false",
        "include-passage-references": "false", "include-first-verse-numbers": "false",
        "include-selahs": "true", "indent-paragraphs": "0", "indent-poetry": "false",
        "include-heading-horizontal-lines": "false",
    })
    req = urllib.request.Request(f"{ESV_API}?{q}", headers={"Authorization": f"Token {key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.load(resp)
    passages = body.get("passages") or []
    if not passages:
        return None
    return re.sub(r"\s+", " ", passages[0]).strip()


def esv_passage(ref, cache, key, verbose):
    base = _SUFFIX.sub(r"\1", ref.strip())
    if base in cache:
        return cache[base]
    if not key:
        return None
    try:
        text = esv_fetch(base, key)
    except Exception as exc:                       # network, 401, quota
        print(f"WARN: ESV fetch failed for {base}: {exc}", file=sys.stderr)
        return None
    if text:
        cache[base] = text
        if verbose:
            print(f"  fetched {base}", file=sys.stderr)
    return text


# ---------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--kjv", default=os.environ.get("KJV_JSON") or (DEFAULT_KJV if os.path.exists(DEFAULT_KJV) else None),
                    help="public-domain KJV JSON file (default corpus/sources/kjv-verified.json)")
    ap.add_argument("--esv-cache", default=DEFAULT_ESV_CACHE)
    ap.add_argument("--translation", choices=["KJV", "ESV"], help="check only this translation")
    ap.add_argument("--ids", help="comma-separated entry ids to check")
    ap.add_argument("--json", help="write per-entry results (with source text) here")
    ap.add_argument("--strict", action="store_true", help="also fail on PUNCT differences")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    with open(args.corpus, encoding="utf-8") as f:
        corpus = json.load(f)
    wanted = set(args.ids.split(",")) if args.ids else None
    kjv = load_kjv(args.kjv) if args.kjv else None
    esv_key = os.environ.get("ESV_API_KEY")
    esv_cache = load_cache(args.esv_cache)
    cache_before = json.dumps(esv_cache, sort_keys=True)
    if not esv_key and (args.translation in (None, "ESV")):
        print("note: ESV_API_KEY not set; ESV entries use the cache only", file=sys.stderr)

    results, counts = [], {}
    for i, e in enumerate(corpus):
        if e.get("kind") != "scripture":
            continue
        if wanted and e["id"] not in wanted:
            continue
        tr = e.get("translation")
        if args.translation and tr != args.translation:
            continue
        ref = e.get("ref", "")
        try:
            parsed, suffix = split_ref(ref)
        except ValueError as exc:
            results.append({"idx": i, "id": e["id"], "ref": ref, "translation": tr,
                            "status": "BAD-REF", "detail": str(exc)})
            continue
        source = None
        if tr == "KJV":
            source = kjv_passage(kjv, parsed) if kjv else None
        elif tr == "ESV":
            source = esv_passage(ref, esv_cache, esv_key, args.verbose)
        status, detail = classify(e.get("text", ""), source, suffix)
        if status == "PARTIAL" and not suffix:
            detail = "unlabelled " + detail
        if status == "UNCHECKED" and tr not in ("KJV", "ESV"):
            detail = f"no source for translation {tr}"
        results.append({"idx": i, "id": e["id"], "ref": ref, "translation": tr,
                        "status": status, "detail": detail,
                        "corpus": e.get("text", ""), "source": source})
        counts[status] = counts.get(status, 0) + 1

    if json.dumps(esv_cache, sort_keys=True) != cache_before:
        save_cache(args.esv_cache, esv_cache)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1); f.write("\n")

    bad = 0
    for r in results:
        s = r["status"]
        show = s not in ("EXACT",) and (s != "UNCHECKED" or args.verbose)
        fails = s in ("CASE", "WORD-DIFF", "BAD-REF") or (s == "PARTIAL" and r["detail"].startswith("unlabelled")) \
            or (args.strict and s == "PUNCT")
        bad += fails
        if show or (args.verbose and s == "EXACT"):
            print(f"[{r['idx']} {r['id']}] {r['ref']} ({r['translation']}): {s}  {r['detail']}")
            if args.verbose and r.get("source") and s not in ("EXACT",):
                print(f"    corpus: {r['corpus']}\n    source: {r['source']}")
    print("summary:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), f"| entries {len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
