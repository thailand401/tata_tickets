/**
 * Git commit (Phase 6) — "Commit".
 *
 * Stages all changes and creates a single commit for the task. It deliberately
 * does NOT push: pushing to a shared remote is left to the developer. Returns
 * the new commit SHA so it can be reported to the dashboard.
 */

import { exec } from "child_process";
import * as vscode from "vscode";

function git(args: string, cwd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    exec(`git ${args}`, { cwd, windowsHide: true }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error((stderr || stdout || error.message).trim()));
        return;
      }
      resolve(stdout.trim());
    });
  });
}

export interface CommitResult {
  sha: string;
  message: string;
}

function renderMessage(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_m, key: string) => vars[key] ?? `{${key}}`);
}

export async function commitAll(
  cwd: vscode.Uri,
  messageTemplate: string,
  vars: Record<string, string>,
): Promise<CommitResult> {
  const root = cwd.fsPath;
  await git("add -A", root);
  const status = await git("status --porcelain", root);
  if (!status) {
    throw new Error("Nothing to commit — the agent produced no file changes.");
  }
  const message = renderMessage(messageTemplate, vars);
  const safe = message.replace(/"/g, '\\"');
  await git(`commit -m "${safe}"`, root);
  const sha = await git("rev-parse HEAD", root);
  return { sha, message };
}
