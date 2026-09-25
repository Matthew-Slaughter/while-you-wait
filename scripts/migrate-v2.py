#!/usr/bin/env python3
"""Migrate plugins/while-you-wait/data/devotionals.json to schema v2.

    python3 scripts/migrate-v2.py            # migrate in place, print report
    python3 scripts/migrate-v2.py --dry-run  # report only, write nothing
    python3 scripts/migrate-v2.py PATH       # migrate another corpus file

What it does (idempotent; re-running on a migrated file is a no-op):

  * assigns deterministic ids to entries that lack one
      scripture  scr-<book3>-<chap3>-<verse3>[-<endverse3>]
                 (+ "-<translation>" when several translations share a ref)
      quote      q-<voice-slug>-<nnnn>, numbered per voice in file order
      other      <kind>-<voice-slug>-<nnnn>  (creed, prayer, hymn)
  * drops exact duplicates (same ref + translation + text), keeping the first
  * adds  added: "0.4.1"  where missing
  * remaps themes through scripts/theme-map.json into the controlled vocab
    (plugins/while-you-wait/data/themes.json), deduplicated, 1-4 per entry
  * rewrites keys in a stable order

The sacred fields -- text, ref, translation, voice, insight -- are never
touched; the script asserts they are byte-identical before writing.
Stdlib only.
"""
import collections
import importlib.util
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
THEME_MAP_PATH = os.path.join(HERE, "theme-map.json")
ADDED_VERSION = "0.4.1"
SACRED = ("text", "ref", "translation", "voice", "insight")
KEY_ORDER = ["id", "kind", "ref", "translation", "text", "voice", "insight",
             "witness", "source", "themes", "added"]
KIND_PREFIX = {"quote": "q", "creed": "creed", "prayer": "prayer", "hymn": "hymn"}


def _load_validator():
    """Reuse the 66-book table and ref parser from validate-corpus.py."""
    spec = importlib.util.spec_from_file_location(
        "validate_corpus", os.path.join(HERE, "validate-corpus.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slugify(voice):
    """'J.I. Packer' -> 'ji-packer'; parentheticals dropped."""
    s = re.sub(r"\([^)]*\)", "", voice or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "anon"


def fmt_entry(e):
    """One entry per line, matching the corpus' existing house style."""
    parts = [f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in e.items()]
    return "  { " + ", ".join(parts) + " }"


def write_corpus(path, entries):
    body = ",\n".join(fmt_entry(e) for e in entries)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + body + "\n]\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    path = args[0] if args else DEFAULT_PATH

    vc = _load_validator()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        vocab = json.load(f)
    with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
        theme_map = json.load(f)
    if not isinstance(data, list):
        print("FAIL: corpus must be a JSON array")
        return 1

    report = collections.OrderedDict()
    problems = []

    # -- 1. drop exact duplicates ---------------------------------------------
    seen_exact = {}
    kept, dropped = [], []
    for i, e in enumerate(data):
        key = (e.get("kind"), e.get("ref"), e.get("translation"), e.get("text"))
        if key in seen_exact:
            dropped.append((i, e.get("ref"), e.get("translation"), seen_exact[key]))
            continue
        seen_exact[key] = i
        kept.append(e)
    report["exact duplicates dropped"] = dropped
    original = {id(e): {k: e.get(k) for k in SACRED} for e in kept}

    # -- 2. ids -------------------------------------------------------------------
    # Scripture refs shared by several translations get a "-<translation>" suffix.
    ref_translations = collections.defaultdict(set)
    for e in kept:
        if e.get("kind") == "scripture":
            ref_translations[e.get("ref")].add((e.get("translation") or "").lower())

    existing_ids = {e["id"] for e in kept if isinstance(e.get("id"), str)}
    # per-slug counters continue after the highest number already in use
    counters = collections.Counter()
    for eid in existing_ids:
        m = re.match(r"^([a-z]+-.+)-(\d{4})$", eid)
        if m:
            counters[m.group(1)] = max(counters[m.group(1)], int(m.group(2)))

    assigned, suffixed = [], []
    for e in kept:
        if isinstance(e.get("id"), str) and e["id"]:
            continue
        kind = e.get("kind")
        if kind == "scripture":
            try:
                sid = vc.scripture_id(e.get("ref", ""))
            except ValueError as exc:
                problems.append(f"{e.get('ref')!r}: cannot build id: {exc}")
                continue
            if len(ref_translations[e.get("ref")]) > 1:
                sid = f"{sid}-{(e.get('translation') or '').lower()}"
                suffixed.append(sid)
        else:
            prefix = KIND_PREFIX.get(kind, kind or "x")
            base = f"{prefix}-{slugify(e.get('voice'))}"
            counters[base] += 1
            sid = f"{base}-{counters[base]:04d}"
        if sid in existing_ids:
            problems.append(f"id collision {sid!r} for {e.get('ref')!r}")
            continue
        existing_ids.add(sid)
        e["id"] = sid
        assigned.append(sid)
    report["ids assigned"] = assigned
    report["ids suffixed with translation (shared ref)"] = suffixed

    # -- 3. added ---------------------------------------------------------------------
    n_added = 0
    for e in kept:
        if "added" not in e:
            e["added"] = ADDED_VERSION
            n_added += 1
    report[f"added: {ADDED_VERSION!r} stamped"] = n_added

    # -- 4. themes ----------------------------------------------------------------------
    remapped_entries = 0
    tag_changes = collections.Counter()
    unmapped = collections.Counter()
    before_tags, after_tags = set(), set()
    for e in kept:
        old = e.get("themes") or []
        before_tags.update(old)
        new = []
        for t in old:
            if t in vocab:
                m = t
            elif t in theme_map:
                m = theme_map[t]
                if m is not None and m not in vocab:
                    problems.append(f"theme-map sends {t!r} to {m!r}, which is not in themes.json")
            else:
                unmapped[t] += 1
                m = None
            if m is not None and m not in new:
                new.append(m)
            if m != t:
                tag_changes[(t, m)] += 1
        if not new:
            problems.append(f"{e.get('id') or e.get('ref')!r}: no themes left after remap ({old})")
        new = new[:4]
        after_tags.update(new)
        if new != old:
            remapped_entries += 1
        e["themes"] = new
    report["entries whose themes changed"] = remapped_entries
    report["distinct tags before -> after"] = f"{len(before_tags)} -> {len(after_tags)}"
    report["tags not in theme-map (dropped)"] = dict(unmapped)
    report["tag remaps (old -> new: entries)"] = {f"{a} -> {b}": n for (a, b), n in
                                                   sorted(tag_changes.items(), key=lambda x: (-x[1], x[0][0]))}

    # -- 5. key order ---------------------------------------------------------------
    reordered = 0
    out = []
    for e in kept:
        ordered = {k: e[k] for k in KEY_ORDER if k in e}
        for k in e:                      # unknown keys go last, untouched
            if k not in ordered:
                ordered[k] = e[k]
        if list(ordered.keys()) != list(e.keys()):
            reordered += 1
        out.append(ordered)
    report["entries with keys reordered"] = reordered

    # -- 6. sacred-field assertion --------------------------------------------------
    for e_old, e_new in zip(kept, out):
        for k in SACRED:
            if original[id(e_old)][k] != e_new.get(k):
                problems.append(f"SACRED FIELD CHANGED: {e_new.get('id')} {k}")
    dup_ids = [i for i, n in collections.Counter(e.get("id") for e in out).items() if n > 1]
    if dup_ids:
        problems.append(f"duplicate ids after migration: {dup_ids}")

    # -- report --------------------------------------------------------------------
    print(f"migrate-v2: {len(data)} entries in, {len(out)} out ({path})")
    for k, v in report.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)}")
            for item in v[:20]:
                print(f"      {item}")
            if len(v) > 20:
                print(f"      ... and {len(v) - 20} more")
        elif isinstance(v, dict):
            print(f"  {k}: {len(v)}")
            for kk, vv in list(v.items())[:60]:
                print(f"      {kk}: {vv}")
            if len(v) > 60:
                print(f"      ... and {len(v) - 60} more")
        else:
            print(f"  {k}: {v}")
    if problems:
        print(f"FAIL: {len(problems)} problem(s); nothing written")
        for p in problems[:50]:
            print("  -", p)
        return 1
    changed = (len(dropped) or assigned or n_added or remapped_entries or reordered)
    if dry_run:
        print("dry run: nothing written" if changed else "dry run: already migrated, no changes")
        return 0
    if not changed:
        print("already migrated: no changes, file untouched")
        return 0
    write_corpus(path, out)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
