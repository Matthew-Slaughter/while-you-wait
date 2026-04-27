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
kind = e.get("kind", "scripture")
text = (e.get("text") or e.get("verse") or "").strip()
ref = e.get("ref", "").strip()
translation = e.get("translation", "").strip()
insight = e.get("insight", "").strip()
voice = e.get("voice", "").strip()

use_color = os.environ.get("CLICOLOR_FORCE") or sys.stdout.isatty() or os.environ.get("WHILE_YOU_WAIT_COLOR") == "1"
if use_color:
    DIM = "\033[2m"; BOLD = "\033[1m"; CYAN = "\033[36m"; GOLD = "\033[33m"; MAGENTA = "\033[35m"; RESET = "\033[0m"
else:
    DIM = BOLD = CYAN = GOLD = MAGENTA = RESET = ""

label = "scripture" if kind == "scripture" else "quote"
text_color = GOLD if kind == "scripture" else MAGENTA
citation = f"{ref} ({translation})" if (kind == "scripture" and translation) else ref

bar_top = f"{DIM}─── while you wait · {label} ───────────────────────{RESET}"
bar_bot = f"{DIM}──────────────────────────────────────────────────{RESET}"

print(bar_top)
print(f"  {text_color}“{text}”{RESET}")
if citation:
    print(f"  {DIM}— {citation}{RESET}")
print()
if insight:
    print(f"  {CYAN}{insight}{RESET}")
if voice and kind != "scripture" and voice not in citation:
    print(f"  {DIM}— {voice}{RESET}")
print(bar_bot)
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
