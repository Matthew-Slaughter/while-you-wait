#!/usr/bin/env python3
"""Shared devotional renderer used by both the Claude Code plugin hook
and the Codex CLI hook.

Usage:
    python3 render_devotional.py <path-to-devotionals.json>

Picks one entry -- uniformly among the least-often-shown entries, skipping
the most-recent N -- renders it as a colored box, and writes a single line
of JSON `{"systemMessage": "..."}` to stdout. That JSON shape is the common
contract for both Claude Code's UserPromptSubmit hook and Codex CLI's
UserPromptSubmit hook — both render it as a TUI message visible to
the user without injecting it into model context.

Per-tool state/config isolation via env vars:
    WHILE_YOU_WAIT_CONFIG   override config JSON path
                            (default: ~/.claude/while-you-wait.json)
    WHILE_YOU_WAIT_STATE    override anti-repeat state JSON path
                            (default: ~/.claude/while-you-wait.state.json)
                            shape: {"recent": [id, ...], "seen": {id: count}}
                            (a bare list, the pre-0.5 format, is read as
                            "recent")
    WHILE_YOU_WAIT_MODE     override border mode (minimal|rich|reverent)
    WHILE_YOU_WAIT_SOUND    override sound (on|off)

Any internal failure (missing corpus, malformed JSON, etc.) degrades
to a silent exit-0. A devotional must never disrupt the user's prompt.

Defensive contract (see docs/audit/redteam-0.4.1.md H4/M1/M8/M9):
  * malformed corpus entries are dropped at load time, never drawn;
  * the state file is rewritten atomically (temp file + os.replace) and
    only after a render has succeeded, so a bad entry never burns a prompt;
  * the only thing ever written to stdout is one JSON object whose sole
    key is "systemMessage".  The shell wrapper re-checks that shape.
"""
import json, math, os, random, re, subprocess, sys, tempfile, unicodedata

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else ""
CONFIG_PATH = os.environ.get(
    "WHILE_YOU_WAIT_CONFIG",
    os.path.expanduser("~/.claude/while-you-wait.json"),
)
STATE_PATH = os.environ.get(
    "WHILE_YOU_WAIT_STATE",
    os.path.expanduser("~/.claude/while-you-wait.state.json"),
)
MIN_RECENT_WINDOW = 15   # don't repeat any of the last N entries ...
RECENT_FRACTION = 0.03   # ... or 3% of the corpus, whichever is larger

def recent_window(n_entries):
    return max(MIN_RECENT_WINDOW, round(RECENT_FRACTION * n_entries))

DEFAULTS = {
    "mode": "rich",                 # minimal | rich | reverent
    "sound": False,
    "sound_file": "/System/Library/Sounds/Glass.aiff",
    "sound_volume": 0.2,
    "width": 64,
}
WIDTH_MIN, WIDTH_MAX = 40, 100
WIDTH_SANE = 1000   # anything beyond this is a typo or an attack, not a terminal

# Strip C0/C1 control characters (incl. ESC) so a corpus entry can never
# inject raw terminal escape sequences into the systemMessage we emit.
# Newline and tab survive: hymn stanzas and catechism Q./A. are multi-line.
# Bidi overrides/isolates and zero-width characters are not control
# characters but would pass through invisibly, so they go too.
_CTRL = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f-\x9f"        # C0/C1 minus \t (\x09) and \n (\x0a)
    r"​-‏﻿"                   # zero-width space/joiners, marks, BOM
    r"‪-‮⁦-⁩]"           # bidi embeddings, overrides, isolates
)
def clean(s):
    return _CTRL.sub("", s) if s else s

# "Jim Elliot (per Elisabeth Elliot)" -> "Jim Elliot" on the attribution line.
_TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")
def display_voice(voice):
    return _TRAILING_PAREN.sub("", voice).strip()

def display_width(s):
    """Terminal cell count: East Asian Wide/Fullwidth (CJK, most emoji)
    take two cells, combining marks take none, everything else one."""
    if s.isascii():
        return len(s)
    n = 0
    eaw = unicodedata.east_asian_width
    combining = unicodedata.combining
    for ch in s:
        if combining(ch):
            continue
        n += 2 if eaw(ch) in ("W", "F") else 1
    return n

def _sane_width(value):
    """Return a clamped int width, or None if the value is not a finite,
    reasonable number (bool, NaN, Infinity, 1e308, strings, ...)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        if not math.isfinite(value) or abs(value) > WIDTH_SANE:
            return None
        return max(WIDTH_MIN, min(int(value), WIDTH_MAX))
    except (ValueError, TypeError, OverflowError):
        return None

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
    width = _sane_width(cfg["width"])
    cfg["width"] = DEFAULTS["width"] if width is None else width
    return cfg

# Fields the renderer reads. `text` must be a non-empty string; the rest
# are optional but, when present, must be strings (JSON null included:
# the validator rejects it, and `None.strip()` would kill the render).
_OPTIONAL_STR_FIELDS = ("ref", "insight", "voice", "translation", "kind")

def entry_ok(e):
    if not isinstance(e, dict):
        return False
    text = e.get("text")
    if text is None:                    # v1 corpora used `verse`
        text = e.get("verse")
    if not isinstance(text, str) or not text.strip():
        return False
    for field in _OPTIONAL_STR_FIELDS:
        if field in e and not isinstance(e[field], str):
            return False
    if "id" in e and not isinstance(e["id"], str):
        return False
    return True

def load_entries():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [e for e in data if entry_ok(e)]

def entry_key(e):
    """Stable identity: the v2 `id` when present, else the v1 composite key."""
    eid = e.get("id")
    if isinstance(eid, str) and eid:
        return eid
    return f"{e.get('kind','')}|{e.get('ref','')}|{(e.get('text') or '')[:40]}"

def load_state():
    """Return {"recent": [key, ...], "seen": {key: count}}.

    Tolerates the pre-0.5 format (a bare list of recent keys) and any
    malformed file by falling back to empty state. Non-string items in
    `recent` and non-positive-int counts in `seen` are discarded rather
    than stringified, so a hand-edited state file cannot permanently eat
    window slots.
    """
    recent, seen = [], {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            recent = [x for x in raw if isinstance(x, str)]
        elif isinstance(raw, dict):
            r = raw.get("recent")
            if isinstance(r, list):
                recent = [x for x in r if isinstance(x, str)]
            s = raw.get("seen")
            if isinstance(s, dict):
                for k, v in s.items():
                    if isinstance(k, str) and isinstance(v, int) \
                            and not isinstance(v, bool) and v > 0:
                        seen[k] = v
    except Exception:
        pass
    return {"recent": recent, "seen": seen}

def save_state(state, window, known_keys):
    """Atomic write: serialize to a temp file in the same directory, then
    os.replace() over the state path. A concurrent reader sees either the
    old file or the new one, never a partial write (audit M8)."""
    tmp = None
    try:
        recent = state["recent"][-window:]
        # forget counts for entries no longer in the corpus
        seen = {k: v for k, v in state["seen"].items() if k in known_keys}
        payload = json.dumps({"recent": recent, "seen": seen}, separators=(",", ":"))
        state_dir = os.path.dirname(STATE_PATH) or "."
        os.makedirs(state_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".wyw-state-", suffix=".tmp", dir=state_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, STATE_PATH)
        tmp = None
    except Exception:
        pass
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass

def choose(entries, state, window):
    """Least-seen picker: uniform among entries with the minimum seen count
    that are not in the recent window."""
    recent_set = set(state["recent"][-window:])
    seen = state["seen"]
    candidates = [e for e in entries if entry_key(e) not in recent_set]
    if not candidates:  # window covers everything (tiny corpus) — fall back
        candidates = entries
    low = min(seen.get(entry_key(e), 0) for e in candidates)
    pool = [e for e in candidates if seen.get(entry_key(e), 0) == low]
    return random.choice(pool)

def play_sound(cfg):
    if not cfg["sound"]:
        return
    sf = cfg.get("sound_file", "")
    if isinstance(sf, str) and sf and os.path.exists(sf):
        try:
            vol = max(0.0, min(1.0, float(cfg.get("sound_volume", 0.2))))
            subprocess.Popen(
                ["afplay", "-v", str(vol), sf],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

def _wrap_line(raw, w):
    """Greedy word wrap measured in terminal cells rather than code points,
    so CJK/emoji lines don't overflow the box. Never breaks inside a word
    (an unbreakable token longer than `w` overflows, as before). Leading
    indentation of the line is kept (hymn stanzas), interior whitespace
    is collapsed (as textwrap did)."""
    stripped = raw.lstrip()
    indent = raw[:len(raw) - len(stripped)].expandtabs(4)
    words = stripped.split()
    if not words:
        return [""]
    lines, cur, cur_w = [], [], display_width(indent)
    for word in words:
        ww = display_width(word)
        if cur and cur_w + 1 + ww > w:
            lines.append(indent + " ".join(cur))
            cur, cur_w = [word], display_width(indent) + ww
        else:
            cur_w += ww + (1 if cur else 0)
            cur.append(word)
    lines.append(indent + " ".join(cur))
    return lines

def wrap_block(s, w):
    if not s:
        return []
    out = []
    for raw in s.splitlines() or [s]:
        out.extend(_wrap_line(raw, w))
    return out

def render(e, cfg):
    mode = cfg["mode"]
    width = cfg["width"]
    inner = width - 4  # account for "  " left padding inside borders

    kind = e.get("kind") or "scripture"
    text = clean((e.get("text") or e.get("verse") or "").strip())
    ref = clean((e.get("ref") or "").strip())
    translation = clean((e.get("translation") or "").strip())
    insight = clean((e.get("insight") or "").strip())
    voice = display_voice(clean((e.get("voice") or "").strip()))

    KIND_LABELS = {"scripture": "scripture", "quote": "quote", "creed": "creed", "prayer": "prayer", "hymn": "hymn"}
    label = KIND_LABELS.get(kind, "scripture")
    citation = f"{ref} ({translation})" if (kind == "scripture" and translation) else ref

    DIM = "\033[2m"; CYAN = "\033[36m"; GOLD = "\033[33m"; MAGENTA = "\033[35m"; BLUE = "\033[34m"; WHITE = "\033[37m"; GREEN = "\033[32m"; RESET = "\033[0m"
    KIND_COLORS = {"scripture": GOLD, "quote": MAGENTA, "creed": BLUE, "prayer": WHITE, "hymn": GREEN}
    text_color = KIND_COLORS.get(kind, GOLD)

    lw = display_width(label)
    if mode == "minimal":
        top_raw = f"─── while you wait · {label} {'─' * max(3, width - 22 - lw)}"
        bot_raw = "─" * width
    elif mode == "reverent":
        top_raw = f"═══ while you wait · {label} {'═' * max(3, width - 22 - lw)}"
        bot_raw = "═" * width
    else:  # rich
        top_raw = f"╭─── while you wait · {label} {'─' * max(3, width - 24 - lw)}╮"
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
    state = load_state()
    window = recent_window(len(entries))
    e = choose(entries, state, window)

    # Render and serialize *before* touching state or stdout: if anything
    # here raises, the state file is untouched and nothing is emitted.
    message = render(e, cfg)
    if not isinstance(message, str) or not message.strip():
        return
    payload = json.dumps({"systemMessage": message})

    key = entry_key(e)
    state["recent"].append(key)
    state["seen"][key] = state["seen"].get(key, 0) + 1
    save_state(state, window, {entry_key(x) for x in entries})
    play_sound(cfg)
    sys.stdout.write(payload)
    sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
