#!/usr/bin/env bash
# while-you-wait (Claude Code hook): emit a devotional via UserPromptSubmit's
# JSON stdout channel. Renders via the shared render_devotional.py module
# (also used by the Codex CLI hook in ../../../codex/).

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="$ROOT/data/devotionals.json"
RENDER="$ROOT/scripts/render_devotional.py"

[ -r "$DATA" ] || exit 0
[ -r "$RENDER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 "$RENDER" "$DATA"

exit 0
