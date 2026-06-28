/**
 * RealtimeSync — lightweight polling sync for the active task.
 *
 * The dashboard exposes a `GET /agent/tasks/{id}` sync endpoint. Rather than
 * holding a websocket, the bridge polls it on an interval and surfaces state
 * changes back to the UI (status bar). This mirrors the dashboard's own
 * polling-based realtime fallback.
 */

import { DashboardClient, TaskRun } from "./api";

export class RealtimeSync {
  private timer: ReturnType<typeof setInterval> | undefined;
  private lastState: string | undefined;

  constructor(
    private readonly getClient: () => Promise<DashboardClient>,
    private readonly getRunId: () => string | undefined,
    private readonly intervalMs: number,
    private readonly onChange: (run: TaskRun) => void,
  ) {}

  start(): void {
    this.stop();
    this.timer = setInterval(() => void this.tick(), Math.max(1000, this.intervalMs));
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
    this.lastState = undefined;
  }

  private async tick(): Promise<void> {
    const runId = this.getRunId();
    if (!runId) {
      this.stop();
      return;
    }
    try {
      const client = await this.getClient();
      const { run } = await client.sync(runId);
      if (run.state !== this.lastState) {
        this.lastState = run.state;
        this.onChange(run);
      }
    } catch {
      // Transient network errors are ignored; the next tick retries.
    }
  }
}
