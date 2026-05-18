#!/usr/bin/env bash
# while-you-wait: emit a devotional via the UserPromptSubmit hook's JSON
# stdout channel, using `systemMessage` so it renders in the Claude Code TUI
# without being injected as additional context for Claude.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="$ROOT/data/devotionals.json"

[ -r "$DATA" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 - "$DATA" <<'PY'
import json, os, random, subprocess, sys, textwrap

DATA_PATH = sys.argv[1]
CONFIG_PATH = os.path.expanduser("~/.claude/while-you-wait.json")

DEFAULTS = {
    "mode": "rich",                 # minimal | rich | reverent
    "sound": False,
    "sound_file": "/System/Library/Sounds/Glass.aiff",
    "sound_volume": 0.2,
    "width": 64,
}

def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
        except Exception:
            pass
    env_mode = os.environ.get("WHILE_YOU_WAIT_MODE")
    if env_mode in ("minimal", "rich", "reverent"):
        cfg["mode"] = env_mode
    env_sound = os.environ.get("WHILE_YOU_WAIT_SOUND")
    if env_sound is not None:
        cfg["sound"] = env_sound.lower() in ("1", "true", "yes", "on")
    if cfg["mode"] not in ("minimal", "rich", "reverent"):
        cfg["mode"] = "rich"
    return cfg

cfg = load_config()
mode = cfg["mode"]

with open(DATA_PATH, "r", encoding="utf-8") as f:
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

label = "scripture" if kind == "scripture" else "quote"
citation = f"{ref} ({translation})" if (kind == "scripture" and translation) else ref

DIM = "\033[2m"
CYAN = "\033[36m"
GOLD = "\033[33m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

text_color = GOLD if kind == "scripture" else MAGENTA

width = max(40, min(int(cfg.get("width", 64)), 100))
inner = width - 4  # account for "  " padding inside borders

if mode == "minimal":
    top_raw = f"─── while you wait · {label} {'─' * max(3, width - 22 - len(label))}"
    bot_raw = "─" * width
elif mode == "reverent":
    top_raw = f"═══ while you wait · {label} {'═' * max(3, width - 22 - len(label))}"
    bot_raw = "═" * width
else:  # rich
    top_raw = f"╭─── while you wait · {label} {'─' * max(3, width - 24 - len(label))}╮"
    bot_raw = f"╰{'─' * (width - 2)}╯"

top = f"{DIM}{top_raw}{RESET}"
bot = f"{DIM}{bot_raw}{RESET}"

if cfg["sound"]:
    sf = cfg.get("sound_file", "")
    if sf and os.path.exists(sf):
        try:
            vol = max(0.0, min(1.0, float(cfg.get("sound_volume", 0.2))))
            subprocess.Popen(
                ["afplay", "-v", str(vol), sf],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

def wrap_block(s, w):
    if not s:
        return []
    out = []
    for raw in s.splitlines() or [s]:
        wrapped = textwrap.wrap(
            raw, width=w,
            break_long_words=False, break_on_hyphens=False,
        ) or [""]
        out.extend(wrapped)
    return out

lines = [top, ""]
quoted = f"“{text}”"
for w in wrap_block(quoted, inner):
    lines.append(f"  {text_color}{w}{RESET}")
if citation:
    lines.append(f"  {DIM}— {citation}{RESET}")
if insight:
    lines.append("")
    for w in wrap_block(insight, inner):
        lines.append(f"  {CYAN}{w}{RESET}")
if voice and kind != "scripture" and voice not in citation:
    lines.append(f"  {DIM}— {voice}{RESET}")
lines.append("")
lines.append(bot)

message = "\n".join(lines)

payload = {"systemMessage": message}
sys.stdout.write(json.dumps(payload))
sys.stdout.flush()
PY

exit 0
