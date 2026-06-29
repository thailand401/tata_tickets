/**
 * Context gathering (Phase 6) — "Hiểu Context / Đọc Project / Đọc Coding
 * Standard / Đọc OpenSpecs".
 *
 * Assembles everything the agent needs before planning:
 *   - the task run + its OpenSpec documents (fetched from the dashboard),
 *   - the repository coding standard file (e.g. CODING_STANDARD.md),
 *   - a shallow summary of the project layout.
 */

import * as vscode from "vscode";
import { DashboardClient, TaskContext } from "../api";

export interface AgentContext {
  task: TaskContext;
  codingStandard: string;
  projectTree: string;
  workspaceRoot: vscode.Uri;
}

const IGNORED = new Set([
  "node_modules",
  ".git",
  "out",
  "dist",
  ".venv",
  "__pycache__",
  ".vscode-test",
]);

function workspaceRoot(): vscode.Uri {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    throw new Error("Open a folder/workspace before running the agent.");
  }
  return folder.uri;
}

async function readCodingStandard(root: vscode.Uri, relPath: string): Promise<string> {
  const uri = vscode.Uri.joinPath(root, relPath);
  try {
    const bytes = await vscode.workspace.fs.readFile(uri);
    return Buffer.from(bytes).toString("utf8");
  } catch {
    return `# No coding standard file found at ${relPath}. Follow common best practices for the project's language and frameworks.`;
  }
}

async function buildTree(root: vscode.Uri, depth = 2): Promise<string> {
  const lines: string[] = [];
  const walk = async (dir: vscode.Uri, prefix: string, level: number): Promise<void> => {
    if (level > depth) {
      return;
    }
    let entries: [string, vscode.FileType][];
    try {
      entries = await vscode.workspace.fs.readDirectory(dir);
    } catch {
      return;
    }
    entries.sort((a, b) => a[0].localeCompare(b[0]));
    for (const [name, type] of entries) {
      if (name.startsWith(".") && name !== ".github") {
        continue;
      }
      if (IGNORED.has(name)) {
        continue;
      }
      const isDir = type === vscode.FileType.Directory;
      lines.push(`${prefix}${name}${isDir ? "/" : ""}`);
      if (isDir) {
        await walk(vscode.Uri.joinPath(dir, name), `${prefix}  `, level + 1);
      }
    }
  };
  await walk(root, "", 1);
  return lines.join("\n");
}

export async function gatherContext(
  client: DashboardClient,
  runId: string,
  codingStandardPath: string,
): Promise<AgentContext> {
  const root = workspaceRoot();
  const [task, codingStandard, projectTree] = await Promise.all([
    client.getContext(runId),
    readCodingStandard(root, codingStandardPath),
    buildTree(root),
  ]);
  return { task, codingStandard, projectTree, workspaceRoot: root };
}
