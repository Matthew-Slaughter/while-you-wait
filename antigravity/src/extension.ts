import * as vscode from "vscode";
import corpusData from "../../plugins/while-you-wait/data/devotionals.json";
import {
  ALL_KINDS,
  Entry,
  entryKey,
  pickEntry,
  renderFull,
  renderShort,
} from "./render";

const corpus = corpusData as Entry[];
const STATE_KEY = "whileYouWait.recentKeys";
const RECENT_WINDOW = 15;

let outputChannel: vscode.OutputChannel | undefined;
let statusItem: vscode.StatusBarItem | undefined;

export function activate(context: vscode.ExtensionContext) {
  const cfg = () => vscode.workspace.getConfiguration("whileYouWait");

  const show = async () => {
    try {
      const allowedKinds = cfg().get<string[]>("kinds") ?? ALL_KINDS;
      const eligible = corpus.filter((e) =>
        allowedKinds.includes(e.kind),
      );
      if (eligible.length === 0) return;

      const recent = context.globalState.get<string[]>(STATE_KEY) ?? [];
      const entry = pickEntry(eligible, recent);
      const newRecent = [...recent, entryKey(entry)].slice(-RECENT_WINDOW);
      await context.globalState.update(STATE_KEY, newRecent);

      const surface = cfg().get<string>("surface") ?? "notification";
      if (surface === "outputChannel") {
        if (!outputChannel) {
          outputChannel = vscode.window.createOutputChannel("while you wait");
        }
        outputChannel.clear();
        outputChannel.appendLine(renderFull(entry, 64));
        outputChannel.show(true);
      } else {
        // Toast notification. Truncated by VS Code if too long;
        // renderShort caps the text body at ~140 chars.
        vscode.window.showInformationMessage(renderShort(entry));
      }
    } catch {
      // A devotional must never disrupt the user's session.
      // Silent fail is the right policy.
    }
  };

  // Command (palette + bindable keybinding).
  context.subscriptions.push(
    vscode.commands.registerCommand("whileYouWait.show", show),
  );

  // Status bar trigger — click to summon a devotional.
  statusItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100,
  );
  statusItem.text = "$(book) wyw";
  statusItem.tooltip = "while you wait — click for a devotional";
  statusItem.command = "whileYouWait.show";
  statusItem.show();
  context.subscriptions.push(statusItem);

  // Auto-show one devotional on startup (configurable).
  if (cfg().get<boolean>("autoShowOnStartup")) {
    show();
  }
}

export function deactivate() {
  outputChannel?.dispose();
  statusItem?.dispose();
}
