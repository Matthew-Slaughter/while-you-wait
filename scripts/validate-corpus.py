#!/usr/bin/env python3
"""Validate the devotionals corpus (schema v2): structure, ids, refs,
translation budgets, theme vocabulary, witness shape, length bounds.

Exits 0 if the corpus is well-formed (warnings allowed), 1 with a report
otherwise. Run directly (uses the shipped corpus) or pass a path:

    python3 scripts/validate-corpus.py
    python3 scripts/validate-corpus.py path/to/devotionals.json

Stdlib only. The 66-book table and ref parser below are also imported by
scripts/migrate-v2.py so there is a single source of truth for ids.
"""
import collections
import difflib
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "plugins", "while-you-wait", "data")
DEFAULT_PATH = os.path.join(DATA_DIR, "devotionals.json")
THEMES_PATH = os.path.join(DATA_DIR, "themes.json")
LICENSES_PATH = os.path.join(ROOT, "LICENSES.md")

REQUIRED = {"id", "kind", "text", "ref", "voice", "insight", "themes"}
VALID_KINDS = {"scripture", "quote", "creed", "prayer", "hymn"}
KEY_ORDER = ["id", "kind", "ref", "translation", "text", "voice", "insight",
             "witness", "source", "themes", "added"]
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # control chars (allow \t, \n)
# Invisible / spoofing characters (audit M1): bidi embeddings, overrides and
# isolates; zero-width space/joiners/marks and BOM; the TUI glyphs Claude Code
# uses for its own turn marker and prompt (so a corpus entry cannot pose as
# the assistant); and runs of 3+ box-drawing characters (fake dialogs).
FORBIDDEN = re.compile(
    r"[\u202a-\u202e\u2066-\u2069\u200b-\u200f\ufeff\u23fa\u276f]"
    r"|[\u2500-\u257f]{3,}"
)
FORBIDDEN_NAMES = {
    "\u23fa": "U+23FA (\u23fa Claude turn marker)",
    "\u276f": "U+276F (\u276f prompt chevron)",
    "\ufeff": "U+FEFF (BOM / zero-width no-break space)",
}

# Text length caps (characters) per kind; insight bounds apply to all kinds.
TEXT_MAX = {"scripture": 420, "quote": 420, "prayer": 420, "hymn": 420, "creed": 700}
TEXT_ABS_MAX = 1500      # hard ceiling for `text` regardless of kind (audit L3)
NEAR_DUP_RATIO = 0.75    # quote texts this similar (difflib) are WARNed as variants
INSIGHT_MIN, INSIGHT_MAX = 120, 360
LEGACY_ADDED = "0.4.1"   # entries migrated from the v1 corpus: insight bounds WARN only

# Translation budgets, counted in verses (via ref ranges), not entries.
# hard = FAIL when exceeded; warn = WARN when exceeded. None = unlimited.
# ESV is frozen per docs/PLAN-0.5.md ("cap 500, ~477 used"): the current corpus
# already holds 477 ESV verses, so the hard line sits at Crossway's 500 and the
# plan's 450 target is a WARN. Every other translation hard-fails at its target.
BUDGETS = {
    "ESV": {"hard": 500, "warn": 450},
    "NLT": {"hard": 450, "warn": 405},
    "CSB": {"hard": 700, "warn": 630},
    "AMP": {"hard": 150, "warn": 135},
    "KJV": {"hard": None, "warn": None},
    "WEB": {"hard": None, "warn": None},
    "ASV": {"hard": None, "warn": None},
    "YALL": {"hard": None, "warn": None},   # only if LICENSES.md clears it
}
VOICE_CAP = 15          # max quote entries per voice
THEMES_MIN, THEMES_MAX = 1, 4
SOURCE_VALUES = {"primary", "attributed"}
WITNESS_KEYS = ("voice", "work", "source", "path", "quote")

# ---------------------------------------------------------------------------
# 66-book table: (canonical name, 3-letter code, chapter count)
# Codes follow USFM lowercased (1co, 1jn, sng, ...), matching the id scheme
# in docs/PLAN-0.5.md ("scr-1co-010-004").
# ---------------------------------------------------------------------------
BOOKS = [
    ("Genesis", "gen", 50), ("Exodus", "exo", 40), ("Leviticus", "lev", 27),
    ("Numbers", "num", 36), ("Deuteronomy", "deu", 34), ("Joshua", "jos", 24),
    ("Judges", "jdg", 21), ("Ruth", "rut", 4), ("1 Samuel", "1sa", 31),
    ("2 Samuel", "2sa", 24), ("1 Kings", "1ki", 22), ("2 Kings", "2ki", 25),
    ("1 Chronicles", "1ch", 29), ("2 Chronicles", "2ch", 36), ("Ezra", "ezr", 10),
    ("Nehemiah", "neh", 13), ("Esther", "est", 10), ("Job", "job", 42),
    ("Psalms", "psa", 150), ("Proverbs", "pro", 31), ("Ecclesiastes", "ecc", 12),
    ("Song of Solomon", "sng", 8), ("Isaiah", "isa", 66), ("Jeremiah", "jer", 52),
    ("Lamentations", "lam", 5), ("Ezekiel", "ezk", 48), ("Daniel", "dan", 12),
    ("Hosea", "hos", 14), ("Joel", "jol", 3), ("Amos", "amo", 9),
    ("Obadiah", "oba", 1), ("Jonah", "jon", 4), ("Micah", "mic", 7),
    ("Nahum", "nam", 3), ("Habakkuk", "hab", 3), ("Zephaniah", "zep", 3),
    ("Haggai", "hag", 2), ("Zechariah", "zec", 14), ("Malachi", "mal", 4),
    ("Matthew", "mat", 28), ("Mark", "mrk", 16), ("Luke", "luk", 24),
    ("John", "jhn", 21), ("Acts", "act", 28), ("Romans", "rom", 16),
    ("1 Corinthians", "1co", 16), ("2 Corinthians", "2co", 13), ("Galatians", "gal", 6),
    ("Ephesians", "eph", 6), ("Philippians", "php", 4), ("Colossians", "col", 4),
    ("1 Thessalonians", "1th", 5), ("2 Thessalonians", "2th", 3), ("1 Timothy", "1ti", 6),
    ("2 Timothy", "2ti", 4), ("Titus", "tit", 3), ("Philemon", "phm", 1),
    ("Hebrews", "heb", 13), ("James", "jas", 5), ("1 Peter", "1pe", 5),
    ("2 Peter", "2pe", 3), ("1 John", "1jn", 5), ("2 John", "2jn", 1),
    ("3 John", "3jn", 1), ("Jude", "jud", 1), ("Revelation", "rev", 22),
]
ALIASES = {
    "psalm": "Psalms", "song of songs": "Song of Songs", "canticles": "Song of Solomon",
    "song of songs": "Song of Solomon", "revelations": "Revelation",
}
BOOK_BY_NAME = {name.lower(): (name, code, chapters) for name, code, chapters in BOOKS}
for _alias, _canon in ALIASES.items():
    BOOK_BY_NAME[_alias] = BOOK_BY_NAME[_canon.lower()]
BOOK_BY_CODE = {code: (name, code, chapters) for name, code, chapters in BOOKS}

# A trailing a/b on the last verse ("Isaiah 6:3b", "Hebrews 1:1-3a") marks a
# deliberate partial verse (policy in docs/audit/redteam-0.4.1.md H3); it is
# accepted here and ignored for ids and verse counts.
_REF_RE = re.compile(r"^\s*((?:[1-3]\s+)?[A-Za-z][A-Za-z ]*?)\s+(\d+)(?::(\d+)(?:\s*[-–]\s*(\d+))?[ab]?)?\s*$")


def parse_ref(ref):
    """Parse 'Book c:v' or 'Book c:v-v2' (or 'Book v' for one-chapter books).

    Returns (book_name, code, chapter, verse_start, verse_end).
    Raises ValueError with a reason if the ref is not a valid single-chapter
    reference to one of the 66 books.
    """
    m = _REF_RE.match(ref or "")
    if not m:
        raise ValueError("does not match 'Book chapter:verse[-verse]'")
    book_raw, a, b, c = m.groups()
    key = re.sub(r"\s+", " ", book_raw.strip()).lower()
    if key not in BOOK_BY_NAME:
        raise ValueError(f"unknown book {book_raw.strip()!r}")
    name, code, chapters = BOOK_BY_NAME[key]
    if b is None:                      # 'Jude 3' style, one-chapter books only
        if chapters != 1:
            raise ValueError("missing verse")
        chapter, v1 = 1, int(a)
    else:
        chapter, v1 = int(a), int(b)
    v2 = int(c) if c is not None else v1
    if not (1 <= chapter <= chapters):
        raise ValueError(f"chapter {chapter} out of range 1-{chapters} for {name}")
    if v1 < 1:
        raise ValueError("verse must be > 0")
    if v2 < v1:
        raise ValueError(f"range end {v2} before start {v1}")
    return name, code, chapter, v1, v2


def scripture_id(ref):
    """Deterministic id for a scripture ref: scr-<book3>-<chap3>-<verse3>[-<end3>]."""
    _, code, chapter, v1, v2 = parse_ref(ref)
    sid = f"scr-{code}-{chapter:03d}-{v1:03d}"
    if v2 != v1:
        sid += f"-{v2:03d}"
    return sid


def verse_count(ref):
    _, _, _, v1, v2 = parse_ref(ref)
    return v2 - v1 + 1


_ID_QUOTE = re.compile(r"^q-[a-z0-9]+(?:-[a-z0-9]+)*-\d{4}$")
_ID_OTHER = re.compile(r"^[a-z]+-[a-z0-9]+(?:-[a-z0-9]+)*$")
_TRANSLATION = re.compile(r"^[A-Z]{2,6}$")


def describe_forbidden(m):
    """Human-readable label for a FORBIDDEN match."""
    hit = m.group(0)
    if len(hit) > 1:
        return f"run of {len(hit)} box-drawing characters {hit!r}"
    if hit in FORBIDDEN_NAMES:
        return FORBIDDEN_NAMES[hit]
    try:
        name = unicodedata.name(hit)
    except ValueError:
        name = "?"
    return f"U+{ord(hit):04X} ({name})"


def normalize_quote(text):
    """Casefold, NFKC-normalize, and drop everything that is not a letter or
    digit, so 'Word, word.' == 'word word' for duplicate detection (audit M3)."""
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def yall_cleared():
    """YALL may be used only if LICENSES.md has a 'YALL:' line not marked pending."""
    try:
        with open(LICENSES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("YALL:"):
                    return "pending" not in line.lower()
    except OSError:
        pass
    return False


def load_themes():
    try:
        with open(THEMES_PATH, "r", encoding="utf-8") as f:
            themes = json.load(f)
        if isinstance(themes, dict):
            return themes
    except (OSError, json.JSONDecodeError):
        pass
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot load {path}: {exc}")
        return 1

    if not isinstance(data, list) or not data:
        print("FAIL: corpus must be a non-empty JSON array")
        return 1

    themes = load_themes()
    errors, warns = [], []
    if themes is None:
        errors.append(f"cannot load theme vocabulary {THEMES_PATH}")
        themes = {}

    ids = collections.Counter()
    by_kind = collections.Counter()
    by_translation_entries = collections.Counter()
    by_translation_verses = collections.Counter()
    quote_voices = collections.Counter()
    all_voices = collections.Counter()
    quote_texts = collections.defaultdict(list)   # normalized text -> [id, ...]
    with_witness = 0
    yall_ok = yall_cleared()

    for i, e in enumerate(data):
        tag = f"[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{tag} entry is not an object")
            continue
        ref = e.get("ref", "?")
        eid = e.get("id")
        tag = f"[{i} {eid or ref}]"
        kind = e.get("kind")

        # --- v1 checks (kept) -------------------------------------------
        missing = REQUIRED - e.keys()
        if missing:
            errors.append(f"{tag} missing keys {sorted(missing)}")
        if kind not in VALID_KINDS:
            errors.append(f"{tag} invalid kind {kind!r}")
        for field in ("text", "ref", "insight", "voice"):
            val = e.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{tag} empty/invalid {field}")
            elif CTRL.search(val):
                errors.append(f"{tag} control characters in {field}")
            else:
                for m in FORBIDDEN.finditer(val):
                    errors.append(f"{tag} forbidden character in {field}: {describe_forbidden(m)}")
        if not isinstance(e.get("themes"), list) or not e.get("themes"):
            errors.append(f"{tag} themes must be a non-empty list")
        translation = (e.get("translation") or "").strip() if isinstance(e.get("translation"), str) else ""
        if kind == "scripture" and not translation:
            errors.append(f"{tag} scripture missing translation")

        unknown_keys = set(e.keys()) - set(KEY_ORDER)
        if unknown_keys:
            warns.append(f"{tag} unknown keys {sorted(unknown_keys)}")

        by_kind[kind] += 1
        all_voices[e.get("voice", "")] += 1

        # --- ids ----------------------------------------------------------
        if not isinstance(eid, str) or not eid:
            errors.append(f"{tag} missing id")
        else:
            ids[eid] += 1
            if kind == "scripture":
                try:
                    expected = scripture_id(ref)
                    ok = eid == expected or (
                        translation and eid == f"{expected}-{translation.lower()}")
                    if not ok:
                        errors.append(f"{tag} id {eid!r} does not match ref (expected {expected!r}"
                                      f"{' or ' + repr(expected + '-' + translation.lower()) if translation else ''})")
                except ValueError:
                    pass  # ref error reported below
            elif kind == "quote":
                if not _ID_QUOTE.match(eid):
                    errors.append(f"{tag} malformed quote id {eid!r} (want q-<voice-slug>-NNNN)")
            elif not _ID_OTHER.match(eid):
                errors.append(f"{tag} malformed id {eid!r} (want lowercase-kebab with a kind prefix)")

        # --- refs / translations (scripture) ------------------------------
        if kind == "scripture":
            try:
                nverses = verse_count(ref)
            except ValueError as exc:
                errors.append(f"{tag} bad ref {ref!r}: {exc}")
                nverses = 0
            if translation:
                if not _TRANSLATION.match(translation):
                    errors.append(f"{tag} translation {translation!r} should be an uppercase code")
                elif translation not in BUDGETS:
                    errors.append(f"{tag} unknown translation {translation!r} (add it to BUDGETS + LICENSES.md)")
                elif translation == "YALL" and not yall_ok:
                    errors.append(f"{tag} YALL used but LICENSES.md has no cleared 'YALL:' line")
                by_translation_entries[translation] += 1
                by_translation_verses[translation] += nverses
        elif translation:
            warns.append(f"{tag} translation set on non-scripture entry")

        # --- quotes: voice cap, source -----------------------------------
        if kind == "quote":
            quote_voices[e.get("voice", "")] += 1
            if isinstance(e.get("text"), str) and e["text"].strip():
                quote_texts[normalize_quote(e["text"])].append((eid if isinstance(eid, str) and eid else f"[{i}]", e["text"]))
            if "source" in e:
                if e["source"] not in SOURCE_VALUES:
                    errors.append(f"{tag} source must be one of {sorted(SOURCE_VALUES)}, got {e['source']!r}")
            else:
                warns.append(f"{tag} quote has no source (primary|attributed); backfill")
        elif "source" in e:
            warns.append(f"{tag} source field on non-quote entry")

        # --- themes ------------------------------------------------------
        th = e.get("themes")
        if isinstance(th, list):
            if not (THEMES_MIN <= len(th) <= THEMES_MAX):
                errors.append(f"{tag} {len(th)} themes; must be {THEMES_MIN}-{THEMES_MAX}")
            if len(set(th)) != len(th):
                errors.append(f"{tag} duplicate themes {th}")
            for t in th:
                if t not in themes:
                    errors.append(f"{tag} theme {t!r} not in themes.json")

        # --- lengths -----------------------------------------------------
        text = e.get("text") if isinstance(e.get("text"), str) else ""
        cap = TEXT_MAX.get(kind)
        if len(text) > TEXT_ABS_MAX:
            errors.append(f"{tag} text is {len(text)} chars; absolute max {TEXT_ABS_MAX}")
        elif cap and len(text) > cap:
            errors.append(f"{tag} text is {len(text)} chars; max {cap} for {kind}")
        insight = e.get("insight") if isinstance(e.get("insight"), str) else ""
        if insight and not (INSIGHT_MIN <= len(insight) <= INSIGHT_MAX):
            msg = f"{tag} insight is {len(insight)} chars; want {INSIGHT_MIN}-{INSIGHT_MAX}"
            (warns if e.get("added") == LEGACY_ADDED else errors).append(msg)

        # --- witness -----------------------------------------------------
        if "witness" in e:
            w = e["witness"]
            if not isinstance(w, dict):
                errors.append(f"{tag} witness must be an object")
            else:
                with_witness += 1
                for k in WITNESS_KEYS:
                    # creed/hymn/prayer entries are verified by their whole
                    # text (verify-witness.py), so witness.quote may be "".
                    if k == "quote" and kind in ("creed", "hymn", "prayer") \
                            and isinstance(w.get(k), str):
                        continue
                    if not isinstance(w.get(k), str) or not w[k].strip():
                        errors.append(f"{tag} witness.{k} must be a non-empty string")
                extra = set(w.keys()) - set(WITNESS_KEYS)
                if extra:
                    warns.append(f"{tag} witness has unknown keys {sorted(extra)}")
                q = w.get("quote")
                # For quotes the witness IS the primary text, so the anchor
                # must appear in `text`; for scripture it anchors the insight.
                if isinstance(q, str) and q.strip():
                    field, where = (text, "text") if kind == "quote" else (insight, "insight")
                    if q not in field:
                        errors.append(f"{tag} witness.quote does not appear verbatim in {where}")

        # --- added -------------------------------------------------------
        added = e.get("added")
        if added is None:
            warns.append(f"{tag} missing added version")
        elif not isinstance(added, str) or not re.match(r"^\d+\.\d+\.\d+$", added):
            errors.append(f"{tag} added must be a semver string, got {added!r}")

    # --- corpus-level checks ------------------------------------------------
    for eid, n in ids.items():
        if n > 1:
            errors.append(f"duplicate id {eid!r} ({n} entries)")
    for tr, verses in sorted(by_translation_verses.items()):
        b = BUDGETS.get(tr, {"hard": None, "warn": None})
        if b["hard"] is not None and verses > b["hard"]:
            errors.append(f"translation {tr}: {verses} verses exceeds hard cap {b['hard']}")
        elif b["warn"] is not None and verses > b["warn"]:
            warns.append(f"translation {tr}: {verses} verses exceeds target {b['warn']} (hard cap {b['hard']})")
    for voice, n in quote_voices.items():
        if n > VOICE_CAP:
            errors.append(f"voice {voice!r} has {n} quotes; cap is {VOICE_CAP}")
    # Duplicate quotes (audit M3): identical after normalization -> FAIL;
    # near-identical wording (translation variants of the same line) -> WARN.
    for norm, hits in quote_texts.items():
        if len(hits) > 1:
            ids = ", ".join(h[0] for h in hits)
            errors.append(f"duplicate quote text ({len(hits)} entries: {ids}): {hits[0][1][:60]!r}")
    uniq = [(norm, hits[0][0]) for norm, hits in quote_texts.items()]
    near = []
    for a in range(len(uniq)):
        na, ida = uniq[a]
        sm = difflib.SequenceMatcher(None, na, "")
        for b in range(a + 1, len(uniq)):
            nb, idb = uniq[b]
            if abs(len(na) - len(nb)) > 0.5 * max(len(na), len(nb), 1):
                continue
            sm.set_seq2(nb)
            if sm.real_quick_ratio() < NEAR_DUP_RATIO or sm.quick_ratio() < NEAR_DUP_RATIO:
                continue
            if sm.ratio() >= NEAR_DUP_RATIO:
                near.append(f"near-duplicate quotes {ida} / {idb} (similarity {sm.ratio():.2f}); keep one")
    warns[0:0] = near   # corpus-level warnings go first so the 50-line cap never hides them

    # --- report ---------------------------------------------------------------
    if warns:
        print(f"WARN: {len(warns)} warning(s):")
        for msg in warns[:50]:
            print("  -", msg)
        if len(warns) > 50:
            print(f"  ... and {len(warns) - 50} more")
    if errors:
        print(f"FAIL: {len(errors)} problem(s) across {len(data)} entries:")
        for msg in errors[:50]:
            print("  -", msg)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")

    print()
    print(f"{'kind':<12}{'entries':>8}")
    for k in ("scripture", "quote", "creed", "prayer", "hymn"):
        if by_kind.get(k):
            print(f"{k:<12}{by_kind[k]:>8}")
    print(f"{'total':<12}{len(data):>8}")
    print()
    print(f"{'translation':<12}{'entries':>8}{'verses':>8}{'hard':>8}")
    for tr in sorted(by_translation_entries):
        hard = BUDGETS.get(tr, {}).get("hard")
        print(f"{tr:<12}{by_translation_entries[tr]:>8}{by_translation_verses[tr]:>8}{str(hard if hard is not None else '-'):>8}")
    print()
    print(f"{'top voices (quotes)':<40}{'n':>4}")
    for voice, n in quote_voices.most_common(10):
        print(f"{voice:<40}{n:>4}")
    print()
    print(f"{'witness':<12}{'entries':>8}")
    print(f"{'with':<12}{with_witness:>8}")
    print(f"{'without':<12}{len(data) - with_witness:>8}")
    print()

    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(warns)} warning(s)")
        return 1
    print(f"OK: {len(data)} entries valid ({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
