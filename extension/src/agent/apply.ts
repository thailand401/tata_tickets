/**
 * File application (Phase 6) — write the agent's generated code to disk.
 *
 * Security: every edit path is resolved against the workspace root and rejected
 * if it escapes it (path traversal / absolute paths). The agent never writes
 * outside the open workspace folder.
 */

import * as path from "path";
import * as vscode from "vscode";
import { FileEdit } from "./llm";

export interface AppliedFile {
  path: string;
  action: "created" | "modified";
}

function safeResolve(root: vscode.Uri, relPath: string): vscode.Uri {
  const normalized = path.normalize(relPath).replace(/^([/\\])+/, "");
  const target = vscode.Uri.joinPath(root, normalized);
  const rootPath = root.fsPath.replace(/[/\\]+$/, "");
  if (target.fsPath !== rootPath && !target.fsPath.startsWith(rootPath + path.sep)) {
    throw new Error(`Refusing to write outside the workspace: ${relPath}`);
  }
  return target;
}

async function exists(uri: vscode.Uri): Promise<boolean> {
  try {
    await vscode.workspace.fs.stat(uri);
    return true;
  } catch {
    return false;
  }
}

export async function applyEdits(
  root: vscode.Uri,
  edits: FileEdit[],
): Promise<AppliedFile[]> {
  const applied: AppliedFile[] = [];
  for (const edit of edits) {
    const uri = safeResolve(root, edit.path);
    const existed = await exists(uri);
    const dir = vscode.Uri.joinPath(uri, "..");
    await vscode.workspace.fs.createDirectory(dir);
    await vscode.workspace.fs.writeFile(uri, Buffer.from(edit.content, "utf8"));
    applied.push({ path: edit.path, action: existed ? "modified" : "created" });
  }
  return applied;
}
