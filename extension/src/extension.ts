/**
 * Tata Agent Bridge — VS Code extension entry point (Phase 5).
 *
 * Bridges the dashboard and the editor: login, pull the next assigned task,
 * and push progress / log / commit / review / error / completion. A lightweight
 * poller provides realtime sync of the active task. This extension is a *bridge*
 * only — it never creates or manages tickets.
 */

import * as vscode from "vscode";
import { DashboardClient, TaskRun } from "./api";
import { RealtimeSync } from "./realtime";

const TOKEN_KEY = "tata.accessToken";

let client: DashboardClient | undefined;
let activeTask: TaskRun | undefined;
let status: vscode.StatusBarItem;
let sync: RealtimeSync | undefined;

function config() {
  const c = vscode.workspace.getConfiguration("tata");
  return {
    dashboardUrl: c.get<string>("dashboardUrl", "http://localhost:8080"),
    categories: c.get<string[]>("categories", []),
    workspaceId: c.get<string>("workspaceId", ""),
    syncIntervalMs: c.get<number>("syncIntervalMs", 5000),
  };
}

async function getClient(context: vscode.ExtensionContext): Promise<DashboardClient> {
  const cfg = config();
  const token = await context.secrets.get(TOKEN_KEY);
  if (!client) {
    client = new DashboardClient(cfg.dashboardUrl, token, cfg.workspaceId || undefined);
  } else {
    client.setToken(token);
  }
  return client;
}

function refreshStatus(): void {
  if (!status) {
    return;
  }
  if (activeTask) {
    status.text = `$(rocket) ${activeTask.task_key}: ${activeTask.state}`;
    status.tooltip = `${activeTask.title} (${activeTask.category})`;
  } else {
    status.text = "$(rocket) Tata: idle";
    status.tooltip = "No active task. Run 'Tata: Pull Next Task'.";
  }
  status.show();
}

export function activate(context: vscode.ExtensionContext): void {
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  context.subscriptions.push(status);
  refreshStatus();

  const register = (id: string, fn: () => Promise<void>) =>
    context.subscriptions.push(
      vscode.commands.registerCommand(id, () =>
        fn().catch((e) => vscode.window.showErrorMessage(`Tata: ${e.message ?? e}`)),
      ),
    );

  register("tata.login", async () => {
    const email = await vscode.window.showInputBox({ prompt: "Dashboard email" });
    if (!email) {
      return;
    }
    const password = await vscode.window.showInputBox({
      prompt: "Dashboard password",
      password: true,
    });
    if (!password) {
      return;
    }
    const c = await getClient(context);
    const token = await c.login(email, password);
    await context.secrets.store(TOKEN_KEY, token);
    c.setToken(token);
    vscode.window.showInformationMessage("Tata: logged in.");
  });

  register("tata.logout", async () => {
    await context.secrets.delete(TOKEN_KEY);
    client?.setToken(undefined);
    vscode.window.showInformationMessage("Tata: logged out.");
  });

  register("tata.pullTask", async () => {
    const c = await getClient(context);
    const task = await c.pullNext(config().categories);
    if (!task) {
      vscode.window.showInformationMessage("Tata: no ready task available.");
      return;
    }
    activeTask = task;
    refreshStatus();
    startSync(context);
    vscode.window.showInformationMessage(
      `Tata: pulled ${task.task_key} — ${task.title} (${task.category}).`,
    );
  });

  register("tata.pushProgress", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const value = await vscode.window.showInputBox({ prompt: "Progress percent (0-100)" });
    const percent = Math.max(0, Math.min(100, Number(value ?? 0)));
    await c.pushProgress(run.id, percent, `Progress ${percent}%`);
    vscode.window.showInformationMessage(`Tata: progress ${percent}%.`);
  });

  register("tata.pushLog", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const message = await vscode.window.showInputBox({ prompt: "Log message" });
    if (!message) {
      return;
    }
    await c.pushLog(run.id, "info", message);
  });

  register("tata.pushCommit", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const sha = await vscode.window.showInputBox({ prompt: "Commit SHA" });
    if (!sha) {
      return;
    }
    const message = (await vscode.window.showInputBox({ prompt: "Commit message" })) ?? "";
    await c.pushCommit(run.id, sha, message);
    vscode.window.showInformationMessage("Tata: commit pushed.");
  });

  register("tata.pushReview", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const statusPick = await vscode.window.showQuickPick(
      ["approved", "changes_requested", "commented"],
      { placeHolder: "Review status" },
    );
    if (!statusPick) {
      return;
    }
    const summary = (await vscode.window.showInputBox({ prompt: "Review summary" })) ?? "";
    await c.pushReview(run.id, statusPick, summary);
    vscode.window.showInformationMessage("Tata: review pushed.");
  });

  register("tata.pushError", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const message = await vscode.window.showInputBox({ prompt: "Error message" });
    if (!message) {
      return;
    }
    const retry = (await vscode.window.showQuickPick(["retry", "give up"], {
      placeHolder: "Retry this task?",
    })) === "retry";
    await c.pushError(run.id, message, retry);
    activeTask = undefined;
    stopSync();
    refreshStatus();
  });

  register("tata.complete", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const summary = (await vscode.window.showInputBox({ prompt: "Completion summary" })) ?? "done";
    await c.complete(run.id, summary, {});
    vscode.window.showInformationMessage(`Tata: ${run.task_key} completed.`);
    activeTask = undefined;
    stopSync();
    refreshStatus();
  });

  register("tata.sync", async () => {
    const run = requireActive();
    const c = await getClient(context);
    const result = await c.sync(run.id);
    activeTask = result.run;
    refreshStatus();
    vscode.window.showInformationMessage(`Tata: ${run.task_key} is ${result.run.state}.`);
  });
}

function requireActive(): TaskRun {
  if (!activeTask) {
    throw new Error("No active task. Pull a task first.");
  }
  return activeTask;
}

function startSync(context: vscode.ExtensionContext): void {
  stopSync();
  if (!activeTask) {
    return;
  }
  sync = new RealtimeSync(
    () => getClient(context),
    () => activeTask?.id,
    config().syncIntervalMs,
    (run) => {
      activeTask = run;
      refreshStatus();
    },
  );
  sync.start();
}

function stopSync(): void {
  sync?.stop();
  sync = undefined;
}

export function deactivate(): void {
  stopSync();
}
