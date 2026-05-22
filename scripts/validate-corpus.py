#!/usr/bin/env python3
"""Validate the devotionals corpus: structure, required keys, value sanity.

Exits 0 if the corpus is well-formed, 1 (with a report) otherwise.
Run directly (uses the shipped corpus) or pass a path:

    python3 scripts/validate-corpus.py
    python3 scripts/validate-corpus.py path/to/devotionals.json
"""
import json
import os
import re
import sys

REQUIRED = {"kind", "text", "ref", "voice", "insight", "themes"}
VALID_KINDS = {"scripture", "quote"}
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # control chars (allow \t, \n)

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "plugins", "while-you-wait", "data", "devotionals.json",
)


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

    errors = []
    for i, e in enumerate(data):
        tag = f"[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{tag} entry is not an object")
            continue
        ref = e.get("ref", "?")
        missing = REQUIRED - e.keys()
        if missing:
            errors.append(f"{tag} {ref}: missing keys {sorted(missing)}")
        if e.get("kind") not in VALID_KINDS:
            errors.append(f"{tag} {ref}: invalid kind {e.get('kind')!r}")
        for field in ("text", "ref", "insight", "voice"):
            val = e.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{tag} {ref}: empty/invalid {field}")
            elif CTRL.search(val):
                errors.append(f"{tag} {ref}: control characters in {field}")
        if not isinstance(e.get("themes"), list) or not e.get("themes"):
            errors.append(f"{tag} {ref}: themes must be a non-empty list")
        if e.get("kind") == "scripture" and not (e.get("translation") or "").strip():
            errors.append(f"{tag} {ref}: scripture missing translation")

    if errors:
        print(f"FAIL: {len(errors)} problem(s) across {len(data)} entries:")
        for msg in errors[:50]:
            print("  -", msg)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1

    print(f"OK: {len(data)} entries valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
