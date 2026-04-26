#!/usr/bin/env bash
# while-you-wait: print a short Scripture + insight on prompt submit.
# Goal: visible to the user, not injected as context for Claude.
# Strategy: write to /dev/tty when available; fall back to stderr.

set -u

DATA="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/data/devotionals.json"

if [ ! -r "$DATA" ]; then
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

OUTPUT=$(python3 - "$DATA" <<'PY'
import json, random, sys, os

with open(sys.argv[1], "r", encoding="utf-8") as f:
    entries = json.load(f)

if not entries:
    sys.exit(0)

e = random.choice(entries)
verse = e.get("verse", "").strip()
ref = e.get("ref", "").strip()
insight = e.get("insight", "").strip()
voice = e.get("voice", "").strip()

use_color = sys.stdout.isatty() or os.environ.get("CLICOLOR_FORCE")
if use_color:
    DIM = "\033[2m"; BOLD = "\033[1m"; CYAN = "\033[36m"; GOLD = "\033[33m"; RESET = "\033[0m"
else:
    DIM = BOLD = CYAN = GOLD = RESET = ""

bar = f"{DIM}─── while you wait ──────────────────────────────{RESET}"
print(bar)
print(f"  {GOLD}“{verse}”{RESET}")
print(f"  {DIM}— {ref}{RESET}")
print()
print(f"  {CYAN}{insight}{RESET}")
if voice:
    print(f"  {DIM}({voice}){RESET}")
print(f"{DIM}──────────────────────────────────────────────────{RESET}")
PY
)

if [ -z "$OUTPUT" ]; then
  exit 0
fi

if { : > /dev/tty; } 2>/dev/null; then
  printf '%s\n' "$OUTPUT" > /dev/tty
else
  printf '%s\n' "$OUTPUT" >&2
fi

exit 0
