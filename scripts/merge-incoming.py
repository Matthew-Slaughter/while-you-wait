#!/usr/bin/env python3
"""Merge reviewed staging files into the corpus.

    python3 scripts/merge-incoming.py corpus/wave1/*.json [--dry-run] [--corpus PATH]

Every staged entry must have a non-empty insight, 1-4 themes, and an id not
already present in the corpus. Appends in file order, writes atomically, and
prints counts by kind. Run validate-corpus.py and verify-witness.py afterwards.
"""
import glob, json, os, sys, collections

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT = os.path.join(ROOT, "plugins", "while-you-wait", "data", "devotionals.json")

def main(argv):
    dry = "--dry-run" in argv
    corpus_path = DEFAULT
    if "--corpus" in argv:
        corpus_path = argv[argv.index("--corpus") + 1]
    pats = [a for a in argv if a.endswith(".json") and a != corpus_path]
    files = sorted(set(f for p in pats for f in glob.glob(p)))
    if not files:
        print("no staging files"); return 1
    with open(corpus_path, encoding="utf-8") as f:
        corpus = json.load(f)
    ids = {e["id"] for e in corpus}
    added, errors = [], []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            staged = json.load(f)
        for e in staged:
            tag = f"{os.path.basename(fp)}:{e.get('id')}"
            if not e.get("id") or e["id"] in ids:
                errors.append(f"{tag}: missing or duplicate id"); continue
            if not isinstance(e.get("insight"), str) or not e["insight"].strip():
                errors.append(f"{tag}: empty insight"); continue
            if not isinstance(e.get("themes"), list) or not (1 <= len(e["themes"]) <= 4):
                errors.append(f"{tag}: themes must have 1-4 tags"); continue
            ids.add(e["id"]); added.append(e)
    if errors:
        print(f"FAIL: {len(errors)} problem(s)"); [print("  -", x) for x in errors[:30]]; return 1
    by_kind = collections.Counter(e["kind"] for e in added)
    print(f"staged {len(added)} entries {dict(by_kind)}; corpus {len(corpus)} -> {len(corpus) + len(added)}")
    if not dry:
        corpus.extend(added)
        tmp = corpus_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=2); f.write("\n")
        os.replace(tmp, corpus_path); print("written", corpus_path)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
