/**
 * Language-model access (Phase 6) — "Sinh Plan" and "Code".
 *
 * Uses the native VS Code Language Model API (`vscode.lm`, e.g. Copilot
 * models), so no API keys are needed. Two responsibilities:
 *   - generatePlan: turn the gathered context into a short, structured plan,
 *   - generateCode: turn the plan (+ any compiler errors from the previous
 *     iteration) into a set of file edits.
 *
 * The model is asked to emit file edits as fenced blocks tagged with the file
 * path: ```ts path=src/foo.ts ... ``` — parseFileEdits extracts them.
 */

import * as vscode from "vscode";
import { AgentContext } from "./context";

export interface FileEdit {
  path: string;
  content: string;
}

export interface Plan {
  summary: string;
  steps: string[];
}

async function selectModel(): Promise<vscode.LanguageModelChat> {
  let models = await vscode.lm.selectChatModels({ vendor: "copilot" });
  if (models.length === 0) {
    models = await vscode.lm.selectChatModels();
  }
  if (models.length === 0) {
    throw new Error(
      "No language model available. Sign in to Copilot (or another provider) and try again.",
    );
  }
  return models[0];
}

async function ask(prompt: string, token: vscode.CancellationToken): Promise<string> {
  const model = await selectModel();
  const messages = [vscode.LanguageModelChatMessage.User(prompt)];
  const response = await model.sendRequest(messages, {}, token);
  let text = "";
  for await (const fragment of response.text) {
    text += fragment;
  }
  return text;
}

function contextBlock(ctx: AgentContext): string {
  const run = ctx.task.run;
  const docs = ctx.task.documents;
  const docText = Object.keys(docs)
    .map((kind) => `### ${kind}: ${docs[kind].title}\n${docs[kind].content}`)
    .join("\n\n");
  return [
    `# Task: ${run.task_key} — ${run.title} (${run.category})`,
    `\n# Coding standard\n${ctx.codingStandard}`,
    `\n# Project layout\n${ctx.projectTree}`,
    `\n# OpenSpec documents\n${docText}`,
  ].join("\n");
}

export async function generatePlan(
  ctx: AgentContext,
  token: vscode.CancellationToken,
): Promise<Plan> {
  const prompt = [
    "You are an autonomous coding agent. Read the task, coding standard, project",
    "layout and OpenSpec documents, then produce a concise implementation plan.",
    "Respond with ONLY a JSON object: {\"summary\": string, \"steps\": string[]}.",
    "",
    contextBlock(ctx),
  ].join("\n");
  const raw = await ask(prompt, token);
  const json = extractJson(raw);
  try {
    const parsed = JSON.parse(json) as Partial<Plan>;
    return {
      summary: parsed.summary ?? "",
      steps: Array.isArray(parsed.steps) ? parsed.steps : [],
    };
  } catch {
    return { summary: raw.slice(0, 500), steps: [] };
  }
}

export async function generateCode(
  ctx: AgentContext,
  plan: Plan,
  previousErrors: string | undefined,
  token: vscode.CancellationToken,
): Promise<FileEdit[]> {
  const fix = previousErrors
    ? [
        "",
        "# Previous compile/test output (FIX THESE ERRORS)",
        previousErrors,
        "Return the full updated content of every file you change to fix them.",
      ].join("\n")
    : "";
  const prompt = [
    "You are an autonomous coding agent. Implement the plan by writing code that",
    "follows the coding standard. For EACH file you create or modify, output a",
    "fenced code block whose info string includes its workspace-relative path:",
    "",
    "```lang path=relative/path/to/file.ext",
    "<full file content>",
    "```",
    "",
    "Output ONLY such fenced blocks — one per file, each with the COMPLETE file",
    "content (not a diff). Do not include any other prose.",
    "",
    `# Plan\n${plan.summary}\n${plan.steps.map((s) => `- ${s}`).join("\n")}`,
    "",
    contextBlock(ctx),
    fix,
  ].join("\n");
  const raw = await ask(prompt, token);
  return parseFileEdits(raw);
}

const FENCE = /```[^\n]*?path=([^\s`]+)[^\n]*\n([\s\S]*?)```/g;

/** Extract `path=...` fenced blocks into file edits. */
export function parseFileEdits(text: string): FileEdit[] {
  const edits: FileEdit[] = [];
  let match: RegExpExecArray | null;
  FENCE.lastIndex = 0;
  while ((match = FENCE.exec(text)) !== null) {
    const path = match[1].trim().replace(/^["']|["']$/g, "");
    const content = match[2].replace(/\n$/, "");
    if (path) {
      edits.push({ path, content });
    }
  }
  return edits;
}

function extractJson(text: string): string {
  const fenced = /```(?:json)?\s*\n([\s\S]*?)```/.exec(text);
  if (fenced) {
    return fenced[1].trim();
  }
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return text.slice(start, end + 1);
  }
  return text.trim();
}
