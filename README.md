# while-you-wait

A small Claude Code plugin that prints a Scripture or theological quote each time you submit a prompt — devotional companionship for Christians while Claude pontificates.

## Preview

Three border modes, three voices from the corpus. In your terminal these are
colored — scripture in **gold**, quotes in **magenta**, creeds in **blue**,
prayers in **white**, the insight in **cyan**, borders dimmed — but GitHub
strips ANSI color from code blocks, so what's below is the monochrome shape.

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

To keep rotation feeling intentional, the last 15 entries shown (or 3% of the corpus, whichever is larger) are tracked in `~/.claude/while-you-wait.state.json` and skipped when picking the next one; the state file is rewritten atomically and only after a successful render. Corpus text is stripped of control, bidi and zero-width characters before rendering, malformed entries are dropped at load time, and the shell wrapper only forwards the renderer's output if it is exactly one JSON object with a single `systemMessage` key — anything else (a stray print, a traceback) is discarded so nothing can leak into Claude's context. Any internal failure (bad config, malformed corpus) degrades to a silent skip, and the hook has a 10-second timeout — the devotional never blocks or disrupts your prompt.

Dependencies: `bash` and `python3` (both ship with macOS). No network calls, no API keys.

## Corpus

The shipped corpus has 1,682 entries, every one traceable to a source a stranger can open:

- **Scripture** spanning all 66 books of the Protestant canon (499 entries; ESV and KJV, each verse checked against the published text)

  Scripture quotations are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. ESV Text Edition: 2025. The ESV text may not be quoted in any publication made available to the public by a Creative Commons license. The ESV may not be translated in whole or in part into any other language. Used by permission. All rights reserved. The corpus stays under Crossway's 500-verse ceiling (`scripts/validate-corpus.py` hard-fails above it); see [`LICENSES.md`](./LICENSES.md).

- **Theologian quotes** (289 entries, 69 voices) from Patristic to contemporary — Augustine, Athanasius, Anselm, Luther, Calvin, the Puritans, Old Princeton, the Dutch Reformed, Lewis, Lloyd-Jones, Bonhoeffer, Packer, Sproul, Piper, Keller, and the devotional women from Susanna Wesley to Joni Eareckson Tada. Every quotation is verbatim from a located source and carries a `witness` that `scripts/verify-witness.py` re-checks in CI.

- **Creeds and catechisms** (701 entries): the Apostles', Nicene, Athanasian and Chalcedonian creeds, the whole Westminster Shorter Catechism, the Heidelberg Catechism, the 1695 Baptist Catechism, and selections from the Westminster Confession, Belgic Confession, Canons of Dort and 1689 London Baptist Confession — text verbatim from public-domain editions.

- **Hymns** (193 stanzas, 28 writers): Watts, Newton, Cowper, Charles Wesley, Gerhardt, Keble, Havergal, Toplady, Ken, Lyte and others, from public-domain hymnals.

Each entry has a `kind` (`scripture` | `quote` | `creed` | `prayer` | `hymn`), a citation, and a one- or two-sentence Reformed-evangelical insight. The `prayer` kind is supported but not yet populated.

**How this was curated.** The 0.4.1 corpus was red-teamed before expansion and found to contain fabricated and misattributed quotations. Every entry was then re-sourced, verified by script, and reviewed by an independent adversarial pass. The full account, the rules every future entry must pass, and the tooling are in [`docs/CURATION.md`](./docs/CURATION.md).

## Install

Everything below, with copy buttons, is on the landing page: [matthew-slaughter.github.io/while-you-wait](https://matthew-slaughter.github.io/while-you-wait/).

### Claude Code

```
/plugin marketplace add Matthew-Slaughter/while-you-wait
/plugin install while-you-wait@while-you-wait
```

Then restart your Claude Code session — hooks load at session start.

To pull updates later:

```
/plugin marketplace update while-you-wait
```

### Claude Desktop: Chat and Cowork tabs

Chat and Cowork have no per-prompt hook, so there the devotional is something Claude includes at the start of a conversation: one entry per day, chosen from the date, printed verbatim by a bundled script. Setup is three steps, once, on the landing page: [matthew-slaughter.github.io/while-you-wait](https://matthew-slaughter.github.io/while-you-wait/). In short: download the skill zip from that page and add it under Settings, Capabilities; paste one sentence into your personal preferences so Claude runs it in every conversation; optionally schedule a daily run in Cowork. The same skill ships inside the Claude Code plugin as `/while-you-wait:while-you-wait` for an on-demand entry.

### Codex CLI

A Codex CLI port lives in [`codex/`](./codex). Clone this repo and add a
`UserPromptSubmit` hook to `~/.codex/config.toml` pointing at
`codex/scripts/show-devotional.sh`. Full instructions in
[`codex/README.md`](./codex/README.md). Same corpus, same renderer,
isolated state.

### Antigravity (and other VS Code-based IDEs)

A VS Code extension lives in [`antigravity/`](./antigravity). Build with
`npm install && npm run package`, then sideload the `.vsix` via Extensions
→ Install from VSIX. Adds a status-bar button + `while you wait: Show
Devotional` command. Note: VS Code's stable API doesn't expose a chat-submit
event, so this version is on-demand rather than automatic. Full
instructions in [`antigravity/README.md`](./antigravity/README.md).

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
| `format` | `auto` \| `box` \| `plain` | `auto` | `plain` is two lines, no color, no box: for the Claude Code desktop app, IDE extensions and the Codex app, which show hook messages as notifications. `auto` picks it when no terminal is detected |
| `debug` | `true` \| `false` | `false` | Writes `~/.claude/while-you-wait.debug.json` (environment, hook input, chosen format) to diagnose rendering on a new client |

**Modes** (border style only — no animation in any mode)
- `minimal` — single-line top and bottom rules, no box corners
- `rich` (default) — rounded box border
- `reverent` — heavier double-line border

**Env var overrides** (useful for one-off testing):
- `WHILE_YOU_WAIT_MODE=reverent`
- `WHILE_YOU_WAIT_SOUND=on`
- `WHILE_YOU_WAIT_FORMAT=plain`

**Desktop app and IDE extensions.** Those surfaces show a hook's message as a plain notification: terminal color codes print raw and each line can be prefixed with the event name. The plugin detects the absence of a terminal and switches to the two-line `plain` format automatically; set `"format": "plain"` in the config file if it guesses wrong.

## Customize the corpus

Edit `plugins/while-you-wait/data/devotionals.json`, then run
`python3 scripts/validate-corpus.py`. Schema v2 (0.5.0):

```json
{
  "id": "scr-psa-046-010",
  "kind": "scripture",
  "ref": "Psalm 46:10",
  "translation": "ESV",
  "text": "Be still, and know that I am God.",
  "voice": "Psalms",
  "insight": "Calvin: ...a verbatim line from a public-domain commentator... Then one sentence of application.",
  "witness": {
    "voice": "John Calvin",
    "work": "Commentary on the Psalms",
    "source": "HistoricalChristianFaith/Commentaries-Database",
    "path": "John Calvin/Psalms 46_10.toml",
    "quote": "a verbatim line from a public-domain commentator"
  },
  "themes": ["rest", "sovereignty"],
  "added": "0.5.0"
}
```

Or for a theologian quote:

```json
{
  "id": "q-augustine-0001",
  "kind": "quote",
  "ref": "Confessions, I.1",
  "text": "You have made us for yourself, O Lord, and our heart is restless until it rests in you.",
  "voice": "Augustine",
  "insight": "context for the quote",
  "source": "primary",
  "themes": ["rest", "knowing-god"],
  "added": "0.5.0"
}
```

Field notes:

- `id` is deterministic and unique. Scripture: `scr-<book3>-<chap3>-<verse3>[-<end3>]`
  (USFM book codes: `gen`, `psa`, `1co`, `1jn`, ...), suffixed `-esv`/`-kjv` when
  one ref ships in two translations. Quotes: `q-<voice-slug>-<nnnn>`. Creeds,
  prayers, and hymns use `<kind>-<voice-slug>-<nnnn>`. `scripts/migrate-v2.py`
  assigns ids to entries that lack one.
- `kind` is `scripture`, `quote`, `creed`, `prayer`, or `hymn` (green; public-domain
  stanzas). Only scripture takes `translation`; each translation has a verse budget
  listed in [LICENSES.md](LICENSES.md).
- `text` is verbatim and never edited. Up to 420 characters (700 for `creed`).
  Newlines are kept, so hymn stanzas and catechism Q./A. render on multiple lines.
- `insight` is 120-360 characters. When it opens with a quoted commentator, the
  optional `witness` object names the author, work, source repo, file path, and the
  exact `quote` substring, which must appear verbatim in `insight`.
- `source` (quotes only) is `primary` (checked against the work) or `attributed`.
- `themes` are 1-4 tags from the controlled vocabulary in
  `plugins/while-you-wait/data/themes.json`.
- `added` is the plugin version that introduced the entry.

## A note on what changed in 0.2.0

Earlier versions wrote directly to `/dev/tty` to render an animated, colored box visible to you but invisible to Claude. Claude Code v2.1.139+ permanently blocks hook access to the controlling terminal, so animation is no longer possible and the script now emits a `systemMessage` JSON payload instead. Colors and box characters survive; the typewriter effect is gone.

## Layout

```
while-you-wait/                              # repo root = marketplace
├── .claude-plugin/marketplace.json          # marketplace manifest
├── .github/workflows/validate.yml           # CI: tests, validator, witness check, hook contract
├── LICENSES.md                              # publisher credit lines and translation caps
├── docs/
│   ├── CURATION.md                          # how the corpus is curated and gated
│   ├── SOURCES.md                           # every source, its license, what we take
│   └── audit/redteam-0.4.1.md               # the audit that started the re-sourcing
├── scripts/
│   ├── validate-corpus.py                   # schema, ids, refs, budgets, themes, duplicates
│   ├── verify-witness.py                    # proves every witness line exists in its source
│   ├── check-scripture.py                   # verse text vs KJV file / ESV API
│   ├── apply-fixes.py                       # applies reviewed patch files with evidence
│   ├── merge-incoming.py                    # appends a reviewed staging wave
│   ├── fetch-sources.sh                     # fetches repo-style sources for verification
│   ├── index-witnesses.py                   # builds the verse -> commentary index
│   ├── ingest-creeds.py, ingest-hymns.py    # verbatim ingest from public-domain sources
│   └── migrate-v2.py                        # one-time schema migration (kept for the record)
├── corpus/
│   ├── fixes/                               # every corpus change, as patch ops with evidence
│   └── incoming/                            # verbatim staged entries awaiting insights
├── tests/test_renderer.py                   # renderer, wrapper and validator tests
├── codex/                                   # Codex CLI port (same renderer, isolated state)
├── antigravity/                             # VS Code / Antigravity extension
└── plugins/
    └── while-you-wait/                      # the plugin itself
        ├── .claude-plugin/plugin.json       # plugin manifest (version bumps on every release)
        ├── hooks/hooks.json                 # registers the UserPromptSubmit hook
        ├── scripts/show-devotional.sh       # wrapper: emits one JSON object or nothing
        ├── scripts/render_devotional.py     # picks and renders an entry (stdlib only)
        └── data/
            ├── devotionals.json             # the corpus
            └── themes.json                  # controlled theme vocabulary
```

`sources/` (git-ignored) holds the fetched source texts and the commentary index; rebuild it with `scripts/fetch-sources.sh` and `scripts/index-witnesses.py`.

## Contributing

Primary text (Scripture, creeds, quotations, hymns) is never edited by hand and never written from memory: it is copied verbatim from a source and carries a `witness` that a script re-verifies. Read [`docs/CURATION.md`](./docs/CURATION.md) first. Before opening a PR, run the same gate CI runs:

```bash
python3 -m unittest discover -s tests
python3 scripts/validate-corpus.py
python3 scripts/verify-witness.py plugins/while-you-wait/data/devotionals.json --fetch
```

To check witnesses the way CI does, from an empty sources directory rather than your local clones:

```bash
T=$(mktemp -d); bash scripts/fetch-sources.sh "$T"
python3 scripts/verify-witness.py plugins/while-you-wait/data/devotionals.json --sources "$T" --fetch
```

Corpus changes go in as patch files under `corpus/fixes/` (format at the top of `scripts/apply-fixes.py`), each operation with its evidence, so every change stays reviewable.

## License

MIT — see [LICENSE](LICENSE).
