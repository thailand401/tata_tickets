/**
 * The autonomous coding-agent loop (Phase 6).
 *
 * Nhận Task → Hiểu Context → Đọc Project/Coding Standard/OpenSpecs → Sinh Plan
 * → Code → Compile → Fix → Loop → Commit. Không Review.
 *
 * Drives a single pulled task to completion: gathers context, plans, generates
 * code, compiles, and fixes compile/test failures in a bounded loop. On success
 * it commits once and reports progress/commit/completion to the dashboard; the
 * review step is intentionally skipped. Sessions and attempts are persisted via
 * the dashboard so the run is fully auditable.
 */

import * as vscode from "vscode";
import { DashboardClient, TaskRun } from "../api";
import { applyEdits } from "./apply";
import { compileAndTest } from "./compile";
import { gatherContext } from "./context";
import { commitAll } from "./git";
import { generateCode, generatePlan } from "./llm";

export interface AgentOptions {
  codingStandardPath: string;
  compileCommand: string;
  testCommand: string;
  maxFixIterations: number;
  commitMessageTemplate: string;
  autoCommit: boolean;
}

export interface AgentOutcome {
  status: "succeeded" | "failed";
  summary: string;
  sha?: string;
}

export async function runAgent(
  client: DashboardClient,
  task: TaskRun,
  options: AgentOptions,
): Promise<AgentOutcome> {
  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `Tata Agent: ${task.task_key}`,
      cancellable: true,
    },
    async (progress, token) => {
      const session = await client.startSession(task.id);
      const report = async (percent: number, message: string): Promise<void> => {
        progress.report({ message });
        await safe(() => client.pushProgress(task.id, percent, message));
        await safe(() => client.pushLog(task.id, "info", message));
      };

      try {
        // -- Context -----------------------------------------------------
        await report(10, "Reading context (project, standard, OpenSpec)…");
        const ctx = await gatherContext(client, task.id, options.codingStandardPath);

        // -- Plan --------------------------------------------------------
        await report(25, "Generating plan…");
        const plan = await generatePlan(ctx, token);
        await safe(() =>
          client.recordPlan(session.id, { summary: plan.summary, steps: plan.steps }),
        );

        // -- Code → Compile → Fix loop -----------------------------------
        let previousErrors: string | undefined;
        let lastFiles: { path: string; action: string }[] = [];
        const maxIter = Math.max(1, options.maxFixIterations);

        for (let iteration = 1; iteration <= maxIter; iteration++) {
          throwIfCancelled(token);
          const phase = iteration === 1 ? "code" : "fix";
          await report(
            25 + Math.round((iteration / maxIter) * 50),
            `${phase === "code" ? "Coding" : "Fixing"} (iteration ${iteration}/${maxIter})…`,
          );

          const edits = await generateCode(ctx, plan, previousErrors, token);
          if (edits.length === 0) {
            previousErrors = "The model returned no file edits. Emit fenced blocks with path=.";
            await recordAttempt(client, session.id, iteration, phase, "fail", "", [], previousErrors);
            continue;
          }
          lastFiles = await applyEdits(ctx.workspaceRoot, edits);

          await report(
            25 + Math.round((iteration / maxIter) * 50),
            `Compiling (iteration ${iteration}/${maxIter})…`,
          );
          const result = await compileAndTest(
            ctx.workspaceRoot,
            options.compileCommand,
            options.testCommand,
          );

          if (result.ok) {
            await recordAttempt(
              client, session.id, iteration, "compile", "pass", result.output, lastFiles,
            );
            return await finishSuccess(client, task, session.id, options, plan.summary, lastFiles);
          }

          previousErrors = result.output;
          await recordAttempt(
            client, session.id, iteration, "compile", "fail", result.output, lastFiles, result.output,
          );
        }

        // -- Exhausted ----------------------------------------------------
        const summary = `Compile did not pass within ${maxIter} iterations.`;
        await safe(() => client.finishSession(session.id, "failed", summary));
        await safe(() => client.pushError(task.id, summary, true));
        return { status: "failed", summary };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        await safe(() => client.finishSession(session.id, "failed", message));
        await safe(() => client.pushError(task.id, message, true));
        return { status: "failed", summary: message };
      }
    },
  );
}

async function finishSuccess(
  client: DashboardClient,
  task: TaskRun,
  sessionId: string,
  options: AgentOptions,
  planSummary: string,
  files: { path: string; action: string }[],
): Promise<AgentOutcome> {
  let sha: string | undefined;
  let summary = planSummary || `Implemented ${task.task_key}`;

  if (options.autoCommit) {
    const commit = await commitAll(
      vscode.workspace.workspaceFolders![0].uri,
      options.commitMessageTemplate,
      { task_key: task.task_key, title: task.title, category: task.category },
    );
    sha = commit.sha;
    summary = commit.message;
    await safe(() => client.recordAttempt(sessionId, {
      iteration: 0, phase: "commit", status: "pass", files,
    }));
    await safe(() => client.pushCommit(task.id, sha!, commit.message));
  }

  // Không Review — go straight to completion.
  await safe(() => client.finishSession(sessionId, "succeeded", summary));
  await safe(() => client.complete(task.id, summary, sha ? { sha } : {}));
  return { status: "succeeded", summary, sha };
}

async function recordAttempt(
  client: DashboardClient,
  sessionId: string,
  iteration: number,
  phase: string,
  status: string,
  output: string,
  files: { path: string; action: string }[],
  error?: string,
): Promise<void> {
  await safe(() =>
    client.recordAttempt(sessionId, {
      iteration,
      phase,
      status,
      compile_output: output,
      files,
      error: error ?? null,
    }),
  );
}

function throwIfCancelled(token: vscode.CancellationToken): void {
  if (token.isCancellationRequested) {
    throw new Error("Agent run cancelled.");
  }
}

/** Best-effort dashboard call: never let a reporting failure abort the loop. */
async function safe(fn: () => Promise<unknown>): Promise<void> {
  try {
    await fn();
  } catch {
    // ignore transient dashboard/reporting errors
  }
}
