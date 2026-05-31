#!/usr/bin/env python3
"""Shared devotional renderer used by both the Claude Code plugin hook
and the Codex CLI hook.

Usage:
    python3 render_devotional.py <path-to-devotionals.json>

Picks one entry at random (skipping the most-recent N already shown),
renders it as a colored box, and writes a single line of JSON
`{"systemMessage": "..."}` to stdout. That JSON shape is the common
contract for both Claude Code's UserPromptSubmit hook and Codex CLI's
UserPromptSubmit hook — both render it as a TUI message visible to
the user without injecting it into model context.

Per-tool state/config isolation via env vars:
    WHILE_YOU_WAIT_CONFIG   override config JSON path
                            (default: ~/.claude/while-you-wait.json)
    WHILE_YOU_WAIT_STATE    override anti-repeat state JSON path
                            (default: ~/.claude/while-you-wait.state.json)
    WHILE_YOU_WAIT_MODE     override border mode (minimal|rich|reverent)
    WHILE_YOU_WAIT_SOUND    override sound (on|off)

Any internal failure (missing corpus, malformed JSON, etc.) degrades
to a silent exit-0. A devotional must never disrupt the user's prompt.
"""
import json, os, random, re, subprocess, sys, textwrap

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else ""
CONFIG_PATH = os.environ.get(
    "WHILE_YOU_WAIT_CONFIG",
    os.path.expanduser("~/.claude/while-you-wait.json"),
)
STATE_PATH = os.environ.get(
    "WHILE_YOU_WAIT_STATE",
    os.path.expanduser("~/.claude/while-you-wait.state.json"),
)
RECENT_WINDOW = 15  # don't repeat any of the last N entries

DEFAULTS = {
    "mode": "rich",                 # minimal | rich | reverent
    "sound": False,
    "sound_file": "/System/Library/Sounds/Glass.aiff",
    "sound_volume": 0.2,
    "width": 64,
}

# Strip C0/C1 control characters (incl. ESC) so a corpus entry can never
# inject raw terminal escape sequences into the systemMessage we emit.
_CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
def clean(s):
    return _CTRL.sub("", s) if s else s

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
    try:
        cfg["width"] = max(40, min(int(cfg["width"]), 100))
    except (ValueError, TypeError):
        cfg["width"] = DEFAULTS["width"]
    return cfg

def load_entries():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]

def entry_key(e):
    return f"{e.get('kind','')}|{e.get('ref','')}|{(e.get('text') or '')[:40]}"

def load_recent():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            recent = json.load(f)
        if isinstance(recent, list):
            return [str(x) for x in recent]
    except Exception:
        pass
    return []

def save_recent(recent):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(recent[-RECENT_WINDOW:], f)
    except Exception:
        pass

def choose(entries, recent):
    recent_set = set(recent)
    candidates = [e for e in entries if entry_key(e) not in recent_set]
    if not candidates:  # window covers everything (tiny corpus) — fall back
        candidates = entries
    return random.choice(candidates)

def play_sound(cfg):
    if not cfg["sound"]:
        return
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

def render(e, cfg):
    mode = cfg["mode"]
    width = cfg["width"]
    inner = width - 4  # account for "  " left padding inside borders

    kind = e.get("kind", "scripture")
    text = clean((e.get("text") or e.get("verse") or "").strip())
    ref = clean(e.get("ref", "").strip())
    translation = clean((e.get("translation") or "").strip())
    insight = clean(e.get("insight", "").strip())
    voice = clean(e.get("voice", "").strip())

    KIND_LABELS = {"scripture": "scripture", "quote": "quote", "creed": "creed", "prayer": "prayer"}
    label = KIND_LABELS.get(kind, "scripture")
    citation = f"{ref} ({translation})" if (kind == "scripture" and translation) else ref

    DIM = "\033[2m"; CYAN = "\033[36m"; GOLD = "\033[33m"; MAGENTA = "\033[35m"; BLUE = "\033[34m"; WHITE = "\033[37m"; RESET = "\033[0m"
    KIND_COLORS = {"scripture": GOLD, "quote": MAGENTA, "creed": BLUE, "prayer": WHITE}
    text_color = KIND_COLORS.get(kind, GOLD)

    if mode == "minimal":
        top_raw = f"─── while you wait · {label} {'─' * max(3, width - 22 - len(label))}"
        bot_raw = "─" * width
    elif mode == "reverent":
        top_raw = f"═══ while you wait · {label} {'═' * max(3, width - 22 - len(label))}"
        bot_raw = "═" * width
    else:  # rich
        top_raw = f"╭─── while you wait · {label} {'─' * max(3, width - 24 - len(label))}╮"
        bot_raw = f"╰{'─' * (width - 2)}╯"

    lines = [f"{DIM}{top_raw}{RESET}", ""]
    for w in wrap_block(f"“{text}”", inner):
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
    lines.append(f"{DIM}{bot_raw}{RESET}")
    return "\n".join(lines)

def main():
    if not DATA_PATH or not os.path.isfile(DATA_PATH):
        return
    cfg = load_config()
    entries = load_entries()
    if not entries:
        return
    recent = load_recent()
    e = choose(entries, recent)
    recent.append(entry_key(e))
    save_recent(recent)
    play_sound(cfg)
    message = render(e, cfg)
    sys.stdout.write(json.dumps({"systemMessage": message}))
    sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
