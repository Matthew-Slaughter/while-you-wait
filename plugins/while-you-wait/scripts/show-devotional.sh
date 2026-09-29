#!/usr/bin/env bash
# while-you-wait (Claude Code hook): emit a devotional via UserPromptSubmit's
# JSON stdout channel. Renders via the shared render_devotional.py module
# (also used by the Codex CLI hook in ../../../codex/).
#
# Output contract (audit H4): this wrapper prints EITHER exactly one JSON
# object whose only key is "systemMessage" (a non-empty string) OR nothing.
# Claude Code treats any other stdout from a UserPromptSubmit hook as
# context for the model, so the renderer's output is captured and
# re-validated here before anything reaches stdout. Always exits 0: a
# devotional must never block or delay a prompt.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="$ROOT/data/devotionals.json"
RENDER="$ROOT/scripts/render_devotional.py"

# The hook-context JSON Claude Code writes to stdin is passed straight through
# to the renderer, which reads it without blocking (select with a short
# timeout), so a stdin that never closes can never stall the hook.

[ -r "$DATA" ] || exit 0
[ -r "$RENDER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# Capture stdout only; stderr (tracebacks) is discarded, never forwarded.
OUT="$(python3 "$RENDER" "$DATA" 2>/dev/null)" || exit 0
[ -n "$OUT" ] || exit 0

# Shape guard, independent of the renderer: parse as JSON, require a single
# object with exactly {"systemMessage": <non-empty str>}, and re-serialize
# it (so only the canonical form is emitted). Anything else -> print nothing.
printf '%s' "$OUT" | python3 -c '
import json, sys
try:
    raw = sys.stdin.read()
    d = json.loads(raw)
    if (isinstance(d, dict) and list(d.keys()) == ["systemMessage"]
            and isinstance(d["systemMessage"], str) and d["systemMessage"].strip()):
        sys.stdout.write(json.dumps({"systemMessage": d["systemMessage"]}))
except Exception:
    pass
' 2>/dev/null

exit 0
