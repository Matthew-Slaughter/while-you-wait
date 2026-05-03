#!/usr/bin/env bash
# while-you-wait: print a Scripture/quote on prompt submit.
# Visible to the user via /dev/tty; not injected as Claude context.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="$ROOT/data/devotionals.json"

[ -r "$DATA" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 - "$DATA" <<'PY'
import json, os, random, shutil, subprocess, sys, textwrap, time

DATA_PATH = sys.argv[1]
CONFIG_PATH = os.path.expanduser("~/.claude/while-you-wait.json")

DEFAULTS = {
    "mode": "rich",                 # minimal | rich | reverent
    "sound": False,
    "sound_file": "/System/Library/Sounds/Glass.aiff",
    "sound_volume": 0.2,
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

try:
    tty = open("/dev/tty", "w")
except OSError:
    tty = sys.stderr

use_color = True
if tty is sys.stderr and not (sys.stderr.isatty() or os.environ.get("CLICOLOR_FORCE")):
    use_color = False

if use_color:
    DIM = "\033[2m"; CYAN = "\033[36m"; GOLD = "\033[33m"; MAGENTA = "\033[35m"; RESET = "\033[0m"
else:
    DIM = CYAN = GOLD = MAGENTA = RESET = ""

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
text_color = GOLD if kind == "scripture" else MAGENTA
citation = f"{ref} ({translation})" if (kind == "scripture" and translation) else ref

term_cols = shutil.get_terminal_size((80, 24)).columns
inner_width = max(40, min(term_cols - 4, 76))

if mode == "minimal":
    bar_top = f"{DIM}─── while you wait · {label} ───{RESET}"
    bar_bot = f"{DIM}{'─' * (inner_width + 4)}{RESET}"
elif mode == "reverent":
    bar_top = f"{DIM}═══ while you wait · {label} {'═' * max(3, inner_width - 18 - len(label))}{RESET}"
    bar_bot = f"{DIM}{'═' * (inner_width + 4)}{RESET}"
else:  # rich
    bar_top = f"{DIM}╭─── while you wait · {label} {'─' * max(3, inner_width - 19 - len(label))}╮{RESET}"
    bar_bot = f"{DIM}╰{'─' * (inner_width + 2)}╯{RESET}"

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

def wrap_block(s, width, indent="  "):
    if not s:
        return []
    lines = []
    for raw in s.splitlines() or [s]:
        wrapped = textwrap.wrap(
            raw, width=width,
            initial_indent="", subsequent_indent="",
            break_long_words=False, break_on_hyphens=False,
        ) or [""]
        lines.extend(indent + w for w in wrapped)
    return lines

buf = [bar_top]
quoted = f"“{text}”"
for i, line in enumerate(wrap_block(quoted, inner_width)):
    body = line[2:]  # strip indent we re-add with color
    buf.append(f"  {text_color}{body}{RESET}")
if citation:
    buf.append(f"  {DIM}— {citation}{RESET}")
buf.append("")
if insight:
    for line in wrap_block(insight, inner_width):
        body = line[2:]
        buf.append(f"  {CYAN}{body}{RESET}")
if voice and kind != "scripture" and voice not in citation:
    buf.append(f"  {DIM}— {voice}{RESET}")
buf.append(bar_bot)

# CRLF line endings: Claude Code's TUI puts the terminal in non-canonical
# mode where bare LF moves the cursor down without returning to column 0,
# which causes our lines to concatenate visually. Leading + trailing blank
# lines push our banner above the area the TUI redraws (thinking spinner).
tty.write("\r\n\r\n" + "\r\n".join(buf) + "\r\n\r\n")
tty.flush()
PY

exit 0
