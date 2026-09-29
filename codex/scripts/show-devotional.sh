#!/usr/bin/env bash
# while-you-wait (Codex CLI hook): emit a devotional via UserPromptSubmit's
# JSON stdout channel. Uses the same renderer and corpus as the Claude
# Code plugin, with isolated state so the two tools don't fight over
# rotation memory.
#
# Env knobs (in addition to the renderer's WHILE_YOU_WAIT_MODE / _SOUND):
#   WHILE_YOU_WAIT_PLAIN=1   strip ANSI color/dim codes from the output
#                            (use if your Codex build shows raw escape codes)
#   WHILE_YOU_WAIT_STATE     override the anti-repeat state file path
#   WHILE_YOU_WAIT_CONFIG    override the config file path

set -u

# Resolve repo root from this script's location (codex/scripts/ -> repo root).
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

DATA="$ROOT/plugins/while-you-wait/data/devotionals.json"
RENDER="$ROOT/plugins/while-you-wait/scripts/render_devotional.py"

[ -r "$DATA" ] || exit 0
[ -r "$RENDER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# Codex's hook-context JSON on stdin is passed through to the renderer, which
# reads it without blocking. Set WHILE_YOU_WAIT_FORMAT=plain (or the legacy
# WHILE_YOU_WAIT_PLAIN=1) for the Codex desktop app; `auto` picks plain when
# no terminal is detected.

# Isolate config/state from the Claude Code plugin's ~/.claude paths.
# Honors CODEX_HOME so multi-account setups (one CODEX_HOME per account)
# each keep their own rotation memory.
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
export WHILE_YOU_WAIT_CONFIG="${WHILE_YOU_WAIT_CONFIG:-$CODEX_DIR/while-you-wait.json}"
export WHILE_YOU_WAIT_STATE="${WHILE_YOU_WAIT_STATE:-$CODEX_DIR/while-you-wait.state.json}"

if [ "${WHILE_YOU_WAIT_PLAIN:-0}" = "1" ]; then
  # Strip ANSI escape sequences from systemMessage while keeping the JSON valid.
  python3 "$RENDER" "$DATA" | python3 -c '
import json, re, sys
raw = sys.stdin.read().strip()
if not raw:
    sys.exit(0)
try:
    d = json.loads(raw)
except Exception:
    sys.stdout.write(raw)
    sys.exit(0)
ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
if isinstance(d.get("systemMessage"), str):
    d["systemMessage"] = ansi.sub("", d["systemMessage"])
sys.stdout.write(json.dumps(d))
'
else
  python3 "$RENDER" "$DATA"
fi

exit 0
