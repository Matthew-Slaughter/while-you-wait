#!/bin/sh
# while you wait: one-line installer for the Claude Code plugin.
#
#   curl -fsSL https://matthew-slaughter.github.io/while-you-wait/install.sh | sh
#
# What it does, and nothing else:
#   1. checks that the `claude` CLI is on your PATH
#   2. claude plugin marketplace add Matthew-Slaughter/while-you-wait
#   3. claude plugin install while-you-wait@while-you-wait
# Read it first if you like; it is 40 lines. Nothing is downloaded by this
# script itself: the plugin comes from GitHub through Claude Code's own
# plugin system, and you can remove it with `claude plugin uninstall`.
set -eu

MARKET="Matthew-Slaughter/while-you-wait"
PLUGIN="while-you-wait@while-you-wait"

say() { printf '%s\n' "$*"; }

if ! command -v claude >/dev/null 2>&1; then
  say "The claude CLI is not on your PATH."
  say "Install Claude Code first: https://code.claude.com/docs/en/setup"
  say "Or, inside any Claude Code session (terminal or desktop app), type:"
  say "  /plugin marketplace add $MARKET"
  say "  /plugin install $PLUGIN"
  exit 1
fi

say "Adding the marketplace..."
claude plugin marketplace add "$MARKET" >/dev/null 2>&1 || claude plugin marketplace update while-you-wait >/dev/null 2>&1 || true

say "Installing the plugin..."
if claude plugin install "$PLUGIN"; then
  say ""
  say "Done. Restart any open Claude Code session; hooks load at session start."
  say "Updates: run  claude plugin update $PLUGIN  now and then,"
  say "or enable auto-update under /plugin > Marketplaces > while-you-wait."
else
  say "Install did not complete. Try inside a Claude Code session:"
  say "  /plugin marketplace add $MARKET"
  say "  /plugin install $PLUGIN"
  exit 1
fi
