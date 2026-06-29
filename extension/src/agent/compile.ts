/**
 * Compile & test (Phase 6) — "Compile".
 *
 * Runs the user-configured compile (and optional test) shell commands in the
 * workspace root via child_process and captures their combined output. A
 * non-zero exit code means the iteration failed; the captured output is fed
 * back to the model on the next "fix" iteration.
 */

import { exec } from "child_process";
import * as vscode from "vscode";

export interface CompileResult {
  ok: boolean;
  output: string;
}

function run(command: string, cwd: string): Promise<CompileResult> {
  return new Promise((resolve) => {
    exec(
      command,
      { cwd, maxBuffer: 10 * 1024 * 1024, windowsHide: true },
      (error, stdout, stderr) => {
        const output = `${stdout || ""}${stderr || ""}`.trim();
        resolve({ ok: !error, output });
      },
    );
  });
}

/**
 * Run the compile command, then (if set and compile passed) the test command.
 * Returns the first failure, or success with the combined output.
 */
export async function compileAndTest(
  cwd: vscode.Uri,
  compileCommand: string,
  testCommand: string | undefined,
): Promise<CompileResult> {
  if (!compileCommand.trim()) {
    throw new Error("Set `tata.compileCommand` before running the agent.");
  }
  const compiled = await run(compileCommand, cwd.fsPath);
  if (!compiled.ok) {
    return { ok: false, output: `$ ${compileCommand}\n${compiled.output}` };
  }
  if (testCommand && testCommand.trim()) {
    const tested = await run(testCommand, cwd.fsPath);
    if (!tested.ok) {
      return { ok: false, output: `$ ${testCommand}\n${tested.output}` };
    }
    return { ok: true, output: `${compiled.output}\n${tested.output}`.trim() };
  }
  return compiled;
}
