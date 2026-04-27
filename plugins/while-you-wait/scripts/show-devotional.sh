#!/usr/bin/env bash
# while-you-wait: print a Scripture/quote on prompt submit.
# Visible to the user via /dev/tty; not injected as Claude context.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="$ROOT/data/devotionals.json"

[ -r "$DATA" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 - "$DATA" <<'PY'
import json, os, random, subprocess, sys, time

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

if mode == "minimal":
    bar_top = f"{DIM}─── while you wait · {label} ───{RESET}"
    bar_bot = f"{DIM}─────────────────────────────────{RESET}"
    typewriter_budget = 0.0
elif mode == "reverent":
    bar_top = f"{DIM}═══ while you wait · {label} ═══════════════════════{RESET}"
    bar_bot = f"{DIM}═══════════════════════════════════════════════════{RESET}"
    typewriter_budget = 0.40
else:  # rich
    bar_top = f"{DIM}╭─── while you wait · {label} ───────────────────────╮{RESET}"
    bar_bot = f"{DIM}╰─────────────────────────────────────────────────╯{RESET}"
    typewriter_budget = 0.10

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

def out(s, end="\n"):
    tty.write(s + end)
    tty.flush()

def typewriter(prefix, body, suffix, total_budget):
    if total_budget <= 0 or not body:
        out(prefix + body + suffix)
        return
    per_char = total_budget / max(1, len(body))
    per_char = max(0.001, min(0.020, per_char))
    tty.write(prefix)
    tty.flush()
    for ch in body:
        tty.write(ch)
        tty.flush()
        time.sleep(per_char)
    tty.write(suffix + "\n")
    tty.flush()

out(bar_top)
typewriter(f"  {text_color}“", text, f"”{RESET}", typewriter_budget)
if citation:
    out(f"  {DIM}— {citation}{RESET}")
out("")
if insight:
    out(f"  {CYAN}{insight}{RESET}")
if voice and kind != "scripture" and voice not in citation:
    out(f"  {DIM}— {voice}{RESET}")
out(bar_bot)
PY

exit 0
