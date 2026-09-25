# while-you-wait — Antigravity / VS Code port

A devotional companion for [Google Antigravity](https://antigravity.google)
(and any VS Code-based IDE) — surfaces a short Scripture or theological
quote on demand.

Same corpus and same picking logic as the Claude Code plugin and Codex CLI
hook in [`../plugins/while-you-wait/`](../plugins/while-you-wait/) and
[`../codex/`](../codex/). Corpus is bundled into the extension at build
time, so the `.vsix` is self-contained.

> **Corpus updates require a rebuild.** `src/extension.ts` imports
> `../../plugins/while-you-wait/data/devotionals.json` and esbuild inlines
> it into `dist/extension.js`. An installed `.vsix` never re-reads the JSON
> from the repo; to pick up new entries, run `npm run package` again and
> reinstall the `.vsix`.

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
| `whileYouWait.kinds` | all five | Which kinds are eligible: `scripture`, `quote`, `creed`, `prayer`, `hymn` |

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

### Corpus schema (v2)

`src/render.ts` mirrors the Python renderer's schema-v2 rules:

- `kind` may be `scripture | quote | creed | prayer | hymn`. A hymn renders
  like a quote: ref line, then voice line.
- Entries may carry optional `id`, `witness`, `source`, `added`. All are
  optional in the `Entry` type, so a v1 corpus still type-checks.
- A `quote` with `source: "attributed"` renders its voice line as
  `— attributed to <voice>`.
- Anti-repeat key: `id` when present, else the legacy
  `kind|ref|text[:40]` key. This matches the Python `entry_key()` rule, so
  a corpus migration does not reset rotation for entries that already had a
  stable key.

Multi-line `text` (hymn stanzas, prayers) keeps its line breaks in the
Output panel and is folded with ` / ` on the one-line toast surface.

### Bundle size

The corpus is inlined into `dist/extension.js` as a JS object literal.
Measured on this machine:

| Corpus | JSON | `dist/extension.js` | `.vsix` (zipped) | esbuild time |
|---|---|---|---|---|
| 804 entries (0.5.x) | 392 KB | 381 KB | 122 KB | <100 ms |
| 4,000 entries, schema v2 (synthetic) | 3.1 MB | 3.2 MB | ~0.7 MB | ~70 ms |

esbuild handles the 3 MB JSON without configuration changes; `vsce` prints
a "file is large" warning above ~300 KB, which is cosmetic. VS Code loads
the bundle once at activation (`onStartupFinished`), so a 3 MB module adds
tens of milliseconds to activation and nothing afterwards.

### Manual verification (no headless path)

Neither VS Code's `code` CLI nor an `antigravity` CLI is on `PATH` here,
and Antigravity ships no `Resources/app/bin` launcher script, so the
`.vsix` cannot be installed or driven from a terminal. Verify by hand:

1. `npm run package` → `while-you-wait-0.1.0.vsix`.
2. Antigravity → Extensions view → `…` → **Install from VSIX…** → pick it.
   (With a `code`/`antigravity` CLI available:
   `<cli> --extensions-dir /tmp/wyw-ext --install-extension while-you-wait-0.1.0.vsix`
   installs into a throwaway extensions dir.)
3. Reload the window. `$(book) wyw` should appear in the status bar and,
   with `autoShowOnStartup` on, one toast should appear.
4. Command Palette → `while you wait: Show Devotional`. Toggle
   `whileYouWait.surface` to `outputChannel` and run it again to see the
   boxed full render.
5. Restrict `whileYouWait.kinds` to `["hymn"]` (once the corpus has hymns)
   and confirm the `hymn` label and the ref-then-voice layout.

The rendering logic itself is exercised headlessly: bundle `src/render.ts`
with esbuild and call `renderShort`/`renderFull`/`pickEntry` from Node
against the corpus plus synthetic v2 entries (what was done when the v2
support landed).

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
- **Corpus is frozen at build time** — rebuild and reinstall the `.vsix`
  after any change to `devotionals.json` (see the note at the top).
- **No `LICENSE` in `antigravity/`** — `vsce` warns about it; the repo-level
  `LICENSE` (MIT) applies. Copy it in before publishing to a marketplace.
