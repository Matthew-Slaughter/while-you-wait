# while-you-wait — Codex CLI port

A devotional companion for [OpenAI Codex CLI](https://github.com/openai/codex) —
prints a short Scripture or theological quote in a colored terminal box
each time you submit a prompt.

Same renderer, same corpus, same anti-repeat rotation as the Claude Code
plugin in [`../plugins/while-you-wait/`](../plugins/while-you-wait/). Only
the wiring differs: this version installs as a Codex `UserPromptSubmit`
hook via `~/.codex/config.toml` instead of a Claude Code plugin manifest.

## Install

1. Clone this repo somewhere stable on your machine:

   ```bash
   git clone https://github.com/Matthew-Slaughter/while-you-wait ~/code/while-you-wait
   ```

2. Open (or create) `~/.codex/config.toml` and append the sections from
   [`config.toml.example`](./config.toml.example), substituting the
   absolute path to your clone:

   ```toml
   [features]
   hooks = true

   [[hooks.UserPromptSubmit]]
   [[hooks.UserPromptSubmit.hooks]]
   type = "command"
   command = "/Users/YOU/code/while-you-wait/codex/scripts/show-devotional.sh"
   timeout = 5
   ```

3. Restart Codex CLI. The next prompt you submit triggers the hook.

## Verify

Run the hook script directly. It should print a single line of JSON
starting with `{"systemMessage":`:

```bash
~/code/while-you-wait/codex/scripts/show-devotional.sh < /dev/null | head -c 80
```

## Configure

Optional config at `~/.codex/while-you-wait.json` (same schema as the
Claude Code plugin):

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

Env var overrides (useful for one-off testing):
- `WHILE_YOU_WAIT_MODE=reverent`
- `WHILE_YOU_WAIT_SOUND=on`

## How it relates to the Claude Code plugin

The repo ships a single corpus that both tools render from:

```
while-you-wait/
├── plugins/while-you-wait/          # Claude Code plugin
│   ├── data/devotionals.json        # ← corpus (source of truth, used by both)
│   └── scripts/
│       ├── render_devotional.py     # ← shared renderer (used by both)
│       └── show-devotional.sh       # Claude Code wrapper
└── codex/                           # this directory
    ├── scripts/show-devotional.sh   # Codex wrapper
    ├── config.toml.example
    └── README.md
```

State and config paths are isolated per tool, so anti-repeat rotation
and your border/sound preferences don't cross-contaminate:

| | Claude Code | Codex CLI |
|---|---|---|
| Install | `/plugin install while-you-wait@while-you-wait` | Clone repo + edit `~/.codex/config.toml` |
| Hook wiring | `plugins/while-you-wait/hooks/hooks.json` | `~/.codex/config.toml` `[[hooks.UserPromptSubmit]]` |
| State path | `~/.claude/while-you-wait.state.json` | `~/.codex/while-you-wait.state.json` |
| Config path | `~/.claude/while-you-wait.json` | `~/.codex/while-you-wait.json` |

## Caveat (verify hands-on)

Codex CLI renders `systemMessage` JSON as a TUI notification. Whether it
preserves ANSI color and box-drawing characters is something to confirm
on first run — if it strips them, the experience is functional but
monochrome. If you want the colored box and color is stripped, file an
issue and we'll explore an alternative render path.
