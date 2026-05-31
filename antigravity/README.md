# while-you-wait — Antigravity / VS Code port

A devotional companion for [Google Antigravity](https://antigravity.google)
(and any VS Code-based IDE) — surfaces a short Scripture or theological
quote on demand.

Same corpus and same picking logic as the Claude Code plugin and Codex CLI
hook in [`../plugins/while-you-wait/`](../plugins/while-you-wait/) and
[`../codex/`](../codex/). Corpus is bundled into the extension at build
time, so the `.vsix` is self-contained.

## What this does (and doesn't)

**Does:**
- Status-bar item `$(book) wyw` — click to summon a devotional
- Command `while you wait: Show Devotional` (Command Palette)
- Bindable to any keyboard shortcut
- Optional auto-show one devotional on Antigravity startup
- Two render surfaces: toast notification (compact) or Output panel (full insight text)

**Doesn't:**
- Fire automatically on every chat-submit. VS Code's stable extension API
  doesn't expose a chat-input-submit event, and Antigravity's native hooks
  system (as of late 2025) doesn't document one either. If/when that
  changes, this extension will pick it up.

## Install (sideload from `.vsix`)

1. Build the `.vsix` (or download a release):

   ```bash
   cd antigravity
   npm install
   npm run package
   ```

   Produces `while-you-wait-0.1.0.vsix`.

2. In Antigravity, open the Extensions view, click the `…` menu →
   **Install from VSIX…**, and pick the file.

3. Reload the window. Look for `$(book) wyw` on the right side of the
   status bar.

## Configure

Open Antigravity settings, search "while you wait":

| Setting | Default | Notes |
|---|---|---|
| `whileYouWait.autoShowOnStartup` | `true` | Show one devotional on Antigravity startup |
| `whileYouWait.surface` | `notification` | `notification` (toast) or `outputChannel` (persistent panel with full text) |
| `whileYouWait.kinds` | all four | Which kinds are eligible: `scripture`, `quote`, `creed`, `prayer` |

Use `outputChannel` if you want the full insight text and the box-drawing
borders — the toast surface truncates and shows only the headline quote.

## Develop

```bash
cd antigravity
npm install        # devDeps only; the extension has no runtime deps
npm run typecheck  # tsc --noEmit
npm run build      # esbuild bundle to dist/extension.js
npm run watch      # rebuild on save
npm run package    # produce a .vsix via @vscode/vsce
```

Open the `antigravity/` folder in VS Code or Antigravity and press F5 to
launch a debug Extension Host with the extension loaded.

## How it relates to the other ports

Single repo, three implementations, one shared corpus:

```
while-you-wait/
├── plugins/while-you-wait/          # Claude Code plugin
│   ├── data/devotionals.json        # ← corpus (source of truth)
│   └── scripts/
│       ├── render_devotional.py     # Python renderer
│       └── show-devotional.sh       # Claude Code hook wrapper
├── codex/                           # Codex CLI port
│   ├── scripts/show-devotional.sh   # reuses the Python renderer
│   └── config.toml.example
└── antigravity/                     # this directory
    ├── src/
    │   ├── render.ts                # TS port of the renderer
    │   └── extension.ts             # VS Code activation + status bar + command
    ├── package.json
    └── README.md
```

State is per-tool:

| | Claude Code | Codex CLI | Antigravity |
|---|---|---|---|
| Anti-repeat state | `~/.claude/while-you-wait.state.json` | `~/.codex/while-you-wait.state.json` | VS Code `globalState` (per-install) |
| Config | `~/.claude/while-you-wait.json` | `~/.codex/while-you-wait.json` | VS Code settings (`whileYouWait.*`) |
| Render | colored ANSI box | colored ANSI box | plain text (toast or Output panel) |

## Caveats

- **No automatic chat-submit hook** — see "What this does (and doesn't)" above.
- **Plain text only** — toast notifications and Output channels don't render
  ANSI color. The toast surface is one-line headline; use `outputChannel`
  surface for the full insight text and box borders.
- **Sideload only** — not yet published to Open VSX. To publish, set up an
  Open VSX publisher account and run `npx ovsx publish *.vsix`.
