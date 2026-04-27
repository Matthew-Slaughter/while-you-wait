# while-you-wait

A small Claude Code plugin that prints a Scripture or theological quote each time you submit a prompt — devotional companionship for Christians while Claude pontificates.

```
╭─── while you wait · scripture ───────────────────────╮
  "Be still, and know that I am God."
  — Psalm 46:10 (ESV)

  Calvin: stillness is not idleness but the soul's posture before sovereignty.
  While you wait, remember Who runs the universe.
╰─────────────────────────────────────────────────╯
```

## How it works

A `UserPromptSubmit` hook fires when you press enter on a prompt. The script picks one entry at random from `data/devotionals.json` and writes it to your terminal (`/dev/tty`, falling back to stderr) so it shows up to you but does **not** become context for Claude.

Dependencies: `bash` and `python3` (both ship with macOS). No network calls, no API keys.

## Corpus

The shipped corpus has ~200 entries:

- **Scripture** spanning all 66 books of the Protestant canon (~140 entries)
- **Theologian quotes** from Patristic to Contemporary voices (~60 entries) — Augustine, Calvin, Luther, Owen, Edwards, Spurgeon, Lewis, Bonhoeffer, Packer, Piper, Keller, Lloyd-Jones, Machen, Athanasius, Anselm, Aquinas, Bavinck, Irenaeus, Polycarp, Tertullian, Cyprian, Bunyan, Watts, Wesley, Newton, Cowper, Sproul, Watson, the Westminster Divines, Chesterton.

Each entry has a `kind` (`scripture` | `quote`), source citation, and a brief Reformed-evangelical insight.

## Install (local marketplace)

```bash
claude plugin marketplace add /path/to/while-you-wait
claude plugin install while-you-wait@while-you-wait
```

Then restart your Claude Code session — hooks load at session start.

After editing the corpus or script, refresh:

```bash
claude plugin marketplace update while-you-wait
```

## Configure

Optional config file at `~/.claude/while-you-wait.json`:

```json
{
  "mode": "rich",
  "sound": false,
  "sound_file": "/System/Library/Sounds/Glass.aiff",
  "sound_volume": 0.2
}
```

| Key | Values | Default | Notes |
|---|---|---|---|
| `mode` | `minimal` \| `rich` \| `reverent` | `rich` | Visual style and animation pacing |
| `sound` | `true` \| `false` | `false` | Plays a chime on render (macOS `afplay`) |
| `sound_file` | path to `.aiff` | `Glass.aiff` | Try `Tink.aiff`, `Ping.aiff`, `Submarine.aiff` |
| `sound_volume` | `0.0`–`1.0` | `0.2` | Soft is good — this fires every prompt |

**Modes**
- `minimal` — single line borders, no animation, fastest
- `rich` (default) — rounded box border, ~100 ms typewriter on the verse
- `reverent` — heavier double-line border, ~400 ms typewriter for contemplative pacing

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

## Layout

```
while-you-wait/                              # repo root = marketplace
├── .claude-plugin/marketplace.json          # marketplace manifest
└── plugins/
    └── while-you-wait/                      # the plugin itself
        ├── .claude-plugin/plugin.json       # plugin manifest
        ├── hooks/hooks.json                 # registers UserPromptSubmit hook
        ├── scripts/show-devotional.sh       # picks an entry and renders it
        └── data/devotionals.json            # the corpus — edit freely
```
