#!/usr/bin/env python3
"""Apply reviewed patch files to the corpus.

    python3 scripts/apply-fixes.py corpus/fixes/*.json [--dry-run] [--corpus PATH]

Patch file: a JSON array of operations, applied in order.

  {"id": "q-spurgeon-0004", "action": "drop",
   "evidence": "fabricated; Spurgeon Library 'quotes Spurgeon didn't say'"}

  {"id": "q-spurgeon-0004", "action": "replace",
   "entry": { ...complete v2 entry, may keep or change the id... },
   "evidence": "verbatim from Sermon 1234 (1875), CCEL full text"}

  {"id": "q-owen-0002", "action": "edit",
   "fields": {"ref": "The Mortification of Sin (1656), ch. 7"},
   "evidence": "chapter corrected against Works vol. 6"}

Rules enforced here: every op needs id, action, evidence; ids must exist
(except a replace whose entry carries a new id, which is then added in
place of the old one); `edit` may not touch `text` on scripture entries
(use `replace` so the change is explicit); `replace` must be a full entry.
Prints a summary; run scripts/validate-corpus.py afterwards.
"""
import json, sys, os, glob

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT = os.path.join(ROOT, "plugins", "while-you-wait", "data", "devotionals.json")

def main(argv):
    dry = "--dry-run" in argv
    corpus_path = DEFAULT
    if "--corpus" in argv:
        corpus_path = argv[argv.index("--corpus") + 1]
    files = [a for a in argv if a.endswith(".json") and a != corpus_path]
    files = sorted(set(f for pat in files for f in glob.glob(pat)))
    if not files:
        print("no patch files"); return 1
    with open(corpus_path, encoding="utf-8") as f:
        corpus = json.load(f)
    index = {e["id"]: i for i, e in enumerate(corpus)}
    stats = {"drop": 0, "replace": 0, "edit": 0}
    errors = []
    for pf in files:
        with open(pf, encoding="utf-8") as f:
            ops = json.load(f)
        for n, op in enumerate(ops):
            tag = f"{os.path.basename(pf)}[{n}]"
            oid, action, ev = op.get("id"), op.get("action"), op.get("evidence")
            if not (oid and action in stats and isinstance(ev, str) and ev.strip()):
                errors.append(f"{tag}: needs id, action(drop|replace|edit), evidence"); continue
            if oid not in index:
                errors.append(f"{tag}: unknown id {oid}"); continue
            i = index[oid]
            if action == "drop":
                corpus[i] = None
            elif action == "replace":
                entry = op.get("entry")
                if not isinstance(entry, dict) or not entry.get("id") or not entry.get("text"):
                    errors.append(f"{tag}: replace needs a full entry with id and text"); continue
                corpus[i] = entry
                if entry["id"] != oid:
                    del index[oid]; index[entry["id"]] = i
            elif action == "edit":
                fields = op.get("fields")
                if not isinstance(fields, dict) or not fields:
                    errors.append(f"{tag}: edit needs fields"); continue
                if corpus[i].get("kind") == "scripture" and "text" in fields:
                    errors.append(f"{tag}: use replace to change scripture text"); continue
                corpus[i].update(fields)
            stats[action] += 1
    if errors:
        print("FAIL:"); [print("  -", e) for e in errors]; return 1
    corpus = [e for e in corpus if e is not None]
    print(f"ops: {stats}  entries now: {len(corpus)}")
    if not dry:
        tmp = corpus_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=2); f.write("\n")
        os.replace(tmp, corpus_path)
        print("written", corpus_path)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
