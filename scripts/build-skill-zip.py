#!/usr/bin/env python3
"""Package the Chat/Cowork skill as a zip for upload to claude.ai.

    python3 scripts/build-skill-zip.py [--out dist/while-you-wait-skill.zip]

Layout inside the zip (what claude.ai expects: SKILL.md at the folder root):
    while-you-wait/SKILL.md
    while-you-wait/scripts/pick.py
    while-you-wait/data/devotionals.json      # copy of the shipped corpus
    while-you-wait/LICENSES.md
"""
import argparse, os, shutil, sys, tempfile, zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILL = os.path.join(ROOT, "plugins", "while-you-wait", "skills", "while-you-wait")
CORPUS = os.path.join(ROOT, "plugins", "while-you-wait", "data", "devotionals.json")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "while-you-wait-skill.zip"))
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    try:
        dst = os.path.join(tmp, "while-you-wait")
        shutil.copytree(SKILL, dst)
        os.makedirs(os.path.join(dst, "data"), exist_ok=True)
        shutil.copy(CORPUS, os.path.join(dst, "data", "devotionals.json"))
        shutil.copy(os.path.join(ROOT, "LICENSES.md"), os.path.join(dst, "LICENSES.md"))
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(dst):
                for fn in sorted(files):
                    if fn.startswith(".") or fn.endswith(".pyc"):
                        continue
                    full = os.path.join(base, fn)
                    z.write(full, os.path.relpath(full, tmp))
        print("wrote", a.out, os.path.getsize(a.out), "bytes")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
