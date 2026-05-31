#!/usr/bin/env bash
# while-you-wait (Codex CLI hook): emit a devotional via UserPromptSubmit's
# JSON stdout channel. Uses the same renderer and corpus as the Claude
# Code plugin, with isolated state so the two tools don't fight over
# rotation memory.

set -u

# Resolve repo root from this script's location (codex/scripts/ -> repo root).
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

DATA="$ROOT/plugins/while-you-wait/data/devotionals.json"
RENDER="$ROOT/plugins/while-you-wait/scripts/render_devotional.py"

[ -r "$DATA" ] || exit 0
[ -r "$RENDER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# Drain Codex's hook context JSON from stdin (we don't need it).
cat >/dev/null

# Isolate config/state from the Claude Code plugin's ~/.claude paths.
export WHILE_YOU_WAIT_CONFIG="${WHILE_YOU_WAIT_CONFIG:-$HOME/.codex/while-you-wait.json}"
export WHILE_YOU_WAIT_STATE="${WHILE_YOU_WAIT_STATE:-$HOME/.codex/while-you-wait.state.json}"

python3 "$RENDER" "$DATA"

exit 0
