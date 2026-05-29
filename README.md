# while-you-wait

A small Claude Code plugin that prints a Scripture or theological quote each time you submit a prompt — devotional companionship for Christians while Claude pontificates.

## Preview

Three border modes, three voices from the corpus. In your terminal these are
colored — scripture in **gold**, quotes in **magenta**, the insight in **cyan**,
borders dimmed — but GitHub strips ANSI color from code blocks, so what's below
is the monochrome shape.

**`minimal`** — single-line top rule, open bottom:

```
─── while you wait · scripture ─────────────────────────────────

  “But they who wait for the Lord shall renew their strength;
  they shall mount up with wings like eagles; they shall run
  and not be weary; they shall walk and not faint.”
  — Isaiah 40:31 (ESV)

  Three modes — fly, run, walk — in descending intensity. The
  hardest may be walking and not fainting. The verbs descend
  on purpose: ordinary endurance is the climax, not the
  consolation prize.

────────────────────────────────────────────────────────────────
```

**`rich`** (default) — rounded box:

```
╭─── while you wait · quote ───────────────────────────────────╮

  “You have made us for yourself, O Lord, and our heart is
  restless until it rests in you.”
  — Confessions, I.1

  The opening confession of the entire work — the existential
  thesis of Christian spirituality. The restlessness is itself
  the homing signal; what frustrates you about every lesser
  rest is the very evidence of what you were made for.
  — Augustine

╰──────────────────────────────────────────────────────────────╯
```

**`reverent`** — heavier double rule:

```
═══ while you wait · scripture ═════════════════════════════════

  “And we know that for those who love God all things work
  together for good, for those who are called according to his
  purpose.”
  — Romans 8:28 (ESV)

  All things — including the failing test, the rejected PR,
  the delayed feature. Providence is not the absence of
  friction but its repurposing. The 'good' is defined in v.
  29: conformity to Christ, not comfort in the present.

════════════════════════════════════════════════════════════════
```

## How it works

A `UserPromptSubmit` hook fires when you press enter on a prompt. The script picks one entry at random from `data/devotionals.json` and emits it as a `systemMessage` — Claude Code renders it to you in the TUI but does **not** add it to Claude's conversation context.

To keep rotation feeling intentional, the last 15 entries shown are tracked in `~/.claude/while-you-wait.state.json` and skipped when picking the next one. Corpus text is stripped of control characters before rendering, and any internal failure (bad config, malformed corpus) degrades to a silent skip — the devotional never blocks or disrupts your prompt.

Dependencies: `bash` and `python3` (both ship with macOS). No network calls, no API keys.

## Corpus

The shipped corpus has ~200 entries:

- **Scripture** spanning all 66 books of the Protestant canon (~140 entries)
- **Theologian quotes** from Patristic to Contemporary voices (~60 entries) — Augustine, Calvin, Luther, Owen, Edwards, Spurgeon, Lewis, Bonhoeffer, Packer, Piper, Keller, Lloyd-Jones, Machen, Athanasius, Anselm, Aquinas, Bavinck, Irenaeus, Polycarp, Tertullian, Cyprian, Bunyan, Watts, Wesley, Newton, Cowper, Sproul, Watson, the Westminster Divines, Chesterton.

Each entry has a `kind` (`scripture` | `quote`), source citation, and a brief Reformed-evangelical insight.

## Install

In Claude Code:

```
/plugin marketplace add Matthew-Slaughter/while-you-wait
/plugin install while-you-wait@while-you-wait
```

Then restart your Claude Code session — hooks load at session start.

To pull updates later:

```
/plugin marketplace update while-you-wait
```

## Configure

Optional config file at `~/.claude/while-you-wait.json`:

```json
{
  "mode": "rich",
  "sound": false,
  "sound_file": "/System/Library/Sounds/Glass.aiff",
  "sound_volume": 0.2,
  "width": 64
}
```

| Key | Values | Default | Notes |
|---|---|---|---|
| `mode` | `minimal` \| `rich` \| `reverent` | `rich` | Border style |
| `sound` | `true` \| `false` | `false` | Plays a chime on render (macOS `afplay`) |
| `sound_file` | path to `.aiff` | `Glass.aiff` | Try `Tink.aiff`, `Ping.aiff`, `Submarine.aiff` |
| `sound_volume` | `0.0`–`1.0` | `0.2` | Soft is good — this fires every prompt |
| `width` | `40`–`100` | `64` | Box width in columns |

**Modes** (border style only — no animation in any mode)
- `minimal` — single-line top and bottom rules, no box corners
- `rich` (default) — rounded box border
- `reverent` — heavier double-line border

**Env var overrides** (useful for one-off testing):
- `WHILE_YOU_WAIT_MODE=reverent`
- `WHILE_YOU_WAIT_SOUND=on`

## Customize the corpus

Edit `plugins/while-you-wait/data/devotionals.json`. Schema:

```json
{
  "kind": "scripture",
  "text": "Be still, and know that I am God.",
  "ref": "Psalm 46:10",
  "translation": "ESV",
  "voice": "Psalms",
  "insight": "1–2 sentence reflection",
  "themes": ["rest", "sovereignty"]
}
```

Or for a theologian quote:

```json
{
  "kind": "quote",
  "text": "Our hearts are restless until they rest in You.",
  "ref": "Confessions, I.1",
  "voice": "Augustine",
  "insight": "context for the quote",
  "themes": ["restlessness"]
}
```

## A note on what changed in 0.2.0

Earlier versions wrote directly to `/dev/tty` to render an animated, colored box visible to you but invisible to Claude. Claude Code v2.1.139+ permanently blocks hook access to the controlling terminal, so animation is no longer possible and the script now emits a `systemMessage` JSON payload instead. Colors and box characters survive; the typewriter effect is gone.

## Layout

```
while-you-wait/                              # repo root = marketplace
├── .claude-plugin/marketplace.json          # marketplace manifest
├── .github/workflows/validate.yml           # CI: corpus + hook checks
├── scripts/validate-corpus.py               # corpus validator (dev tool)
└── plugins/
    └── while-you-wait/                      # the plugin itself
        ├── .claude-plugin/plugin.json       # plugin manifest
        ├── hooks/hooks.json                 # registers UserPromptSubmit hook
        ├── scripts/show-devotional.sh       # picks an entry and renders it
        └── data/devotionals.json            # the corpus — edit freely
```

## Contributing

After editing the corpus, validate it before opening a PR (CI runs the same check):

```bash
python3 scripts/validate-corpus.py
```

## License

MIT — see [LICENSE](LICENSE).
