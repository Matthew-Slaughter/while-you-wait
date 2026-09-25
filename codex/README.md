# while-you-wait — Codex CLI port

A devotional companion for [OpenAI Codex CLI](https://github.com/openai/codex) —
prints a short Scripture or theological quote in a colored terminal box
each time you submit a prompt.

Same renderer, same corpus, same anti-repeat rotation as the Claude Code
plugin in [`../plugins/while-you-wait/`](../plugins/while-you-wait/). Only
the wiring differs: this version installs as a Codex `UserPromptSubmit`
hook via `~/.codex/config.toml` instead of a Claude Code plugin manifest.

Verified against Codex CLI 0.153.x and the hooks docs at
<https://learn.chatgpt.com/docs/hooks> (formerly developers.openai.com/codex/hooks).

## Install

1. Clone this repo somewhere stable on your machine:

   ```bash
   git clone https://github.com/Matthew-Slaughter/while-you-wait ~/code/while-you-wait
   ```

2. Open (or create) `~/.codex/config.toml` and append the section from
   [`config.toml.example`](./config.toml.example), substituting the
   absolute path to your clone:

   ```toml
   [[hooks.UserPromptSubmit]]

   [[hooks.UserPromptSubmit.hooks]]
   type = "command"
   command = "/Users/YOU/code/while-you-wait/codex/scripts/show-devotional.sh"
   timeout = 5
   statusMessage = "while you wait"
   ```

   Hooks are enabled by default in current Codex builds. If you're on an
   older build that still gates them behind a feature flag, also add
   `[features]` / `hooks = true` (harmless on newer builds).

   Alternatively, the same hook can live in `~/.codex/hooks.json` (JSON
   form, same event/handler structure) or in a repo-local
   `.codex/config.toml` for a trusted project. See the Codex docs.

3. Restart Codex CLI. **On first launch Codex shows a "Hooks need review"
   prompt** — choose *Trust all and continue* (or *Review hooks* and trust
   this one). Until it is trusted, the hook is listed but never runs. If you
   later edit the script, Codex flags it as "Modified since last trusted"
   and asks again.

4. Submit any prompt. The devotional box appears above the assistant's
   reply as a hook system message.

## Verify

Run the hook script directly. It should print a single line of JSON
starting with `{"systemMessage":`:

```bash
~/code/while-you-wait/codex/scripts/show-devotional.sh < /dev/null | head -c 80
```

Then, inside Codex, open the hooks panel (Tools & setup → Hooks) and
confirm the hook shows as *Trusted* and *Active* under
"When the user submits a prompt".

Manual end-to-end check: start `codex` in any directory, submit a prompt
such as `say hi`, and confirm the devotional box is rendered. If the box
shows literal `[2m`/`[0m` sequences instead of dim/colored text, set
`WHILE_YOU_WAIT_PLAIN=1` in your shell (or in the hook command, e.g.
`command = "env WHILE_YOU_WAIT_PLAIN=1 /path/to/show-devotional.sh"`) to
emit a monochrome box.

## Configure

Optional config at `~/.codex/while-you-wait.json` (same schema as the
Claude Code plugin). If you run Codex with a custom `CODEX_HOME`, the
config and state files live under that directory instead of `~/.codex`.

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
- `WHILE_YOU_WAIT_PLAIN=1` — strip ANSI color codes (Codex wrapper only)
- `WHILE_YOU_WAIT_STATE=/path/to/state.json` — override the rotation state file

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
| State path | `~/.claude/while-you-wait.state.json` | `$CODEX_HOME/while-you-wait.state.json` (default `~/.codex/`) |
| Config path | `~/.claude/while-you-wait.json` | `$CODEX_HOME/while-you-wait.json` (default `~/.codex/`) |

## How Codex renders the output

Per the Codex hooks docs, a hook's `systemMessage` string is "surfaced as
a warning in the UI or event stream". That means the devotional appears
in the transcript as a hook message (warning styling), not as model
context — it never reaches the model and never affects the reply.

What has been verified hands-on: the script emits valid single-line JSON
and Codex 0.153.x accepts the config shape above. What has *not* yet been
verified in a live TUI session: whether ANSI color and box-drawing
characters survive the warning renderer. If they don't, use
`WHILE_YOU_WAIT_PLAIN=1` (above) and please file an issue with a screenshot.

## Non-interactive use

`codex exec` also runs `UserPromptSubmit` hooks, but only trusted ones.
For automation that has already vetted the hook, Codex provides
`--dangerously-bypass-hook-trust`; we do not recommend it for everyday use.
