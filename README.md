# while-you-wait

A small Claude Code plugin that prints a short Scripture and theological insight each time you submit a prompt — devotional companionship for Christians while Claude pontificates.

```
─── while you wait ──────────────────────────────
  "Be still, and know that I am God."
  — Psalm 46:10 (ESV)

  Calvin: stillness is not idleness but the soul's posture before sovereignty.
  While you wait, remember Who runs the universe — and Who does not need your hurry.
  (John Calvin)
──────────────────────────────────────────────────
```

## How it works

A `UserPromptSubmit` hook fires the moment you press enter on a prompt. It picks one entry at random from `data/devotionals.json` and writes it to your terminal (`/dev/tty`, falling back to stderr) so it shows up to you but does **not** become context for Claude.

Dependencies: `bash` and `python3` (both ship with macOS). No network calls, no API keys.

## Install (local marketplace)

The simplest way to use it from this checkout:

```bash
# Tell Claude Code about a local marketplace at this path:
claude plugin marketplace add /Users/matthewslaughter/Projects/while-you-wait
claude plugin install while-you-wait
```

Or, drop it into any existing local marketplace directory you maintain.

## Customize

Edit `data/devotionals.json`. Each entry is:

```json
{
  "verse": "...",
  "ref": "Book Chapter:Verse (TRANSLATION)",
  "insight": "1–2 sentence reflection",
  "voice": "attribution (theologian or book name)"
}
```

Translation mix follows the maintainer's preferences (AMP / ESV / NIV / MSG / TPT) with a Reformed-evangelical theological frame.

## Layout

```
while-you-wait/                              # repo root = marketplace
├── .claude-plugin/marketplace.json          # marketplace manifest
└── plugins/
    └── while-you-wait/                      # the plugin itself
        ├── .claude-plugin/plugin.json       # plugin manifest
        ├── hooks/hooks.json                 # registers UserPromptSubmit hook
        ├── scripts/show-devotional.sh       # picks a random entry and prints it
        └── data/devotionals.json            # the corpus — edit freely
```
