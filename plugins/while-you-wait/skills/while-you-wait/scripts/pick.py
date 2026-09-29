#!/usr/bin/env python3
"""Pick one devotional entry and print it as plain text (stdlib only).

    python3 pick.py                 # today's entry (deterministic from the date)
    python3 pick.py --random        # a fresh entry
    python3 pick.py --kind hymn     # scripture | quote | creed | prayer | hymn
    python3 pick.py --theme grace   # any theme tag from the corpus
    python3 pick.py --json          # the raw entry

Looks for the corpus next to this skill (data/devotionals.json, the claude.ai
zip layout) or in the parent plugin (../../data/devotionals.json).
"""
import argparse, datetime, hashlib, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(HERE, "..", "data", "devotionals.json"),
    os.path.join(HERE, "..", "..", "..", "data", "devotionals.json"),
]
_STRIP = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]")

def load():
    for p in CANDIDATES:
        p = os.path.normpath(p)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return [e for e in data if isinstance(e, dict) and isinstance(e.get("text"), str) and e["text"].strip()]
    return []

def clean(s):
    return _STRIP.sub("", s or "").strip()

def voice_display(v):
    return re.sub(r"\s*\([^)]*\)\s*$", "", v or "").strip()

def render(e):
    kind = e.get("kind") or "scripture"
    text = clean(e.get("text")).replace("\n", " / ")
    ref = clean(e.get("ref")); tr = clean(e.get("translation")); ins = clean(e.get("insight"))
    voice = voice_display(clean(e.get("voice")))
    cite = f"{ref} ({tr})" if kind == "scripture" and tr else ref
    first = f"“{text}”" + (f" — {cite}" if cite else "")
    if not ins:
        return first
    second = ins + (f" — {voice}" if voice and kind != "scripture" and voice not in cite else "")
    return first + "\n\n" + second

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--kind")
    ap.add_argument("--theme")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--date", help="YYYY-MM-DD (testing)")
    a = ap.parse_args()
    entries = load()
    if a.kind:
        entries = [e for e in entries if e.get("kind") == a.kind]
    if a.theme:
        entries = [e for e in entries if a.theme.lower() in [t.lower() for t in e.get("themes", [])]]
    if not entries:
        return 0
    entries.sort(key=lambda e: e.get("id") or e.get("ref") or "")
    if a.random:
        e = random.choice(entries)
    else:
        day = a.date or datetime.date.today().isoformat()
        h = int(hashlib.sha256(day.encode()).hexdigest(), 16)
        e = entries[h % len(entries)]
    sys.stdout.write(json.dumps(e, ensure_ascii=False) if a.json else render(e))
    sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
