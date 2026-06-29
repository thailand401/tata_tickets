/**
 * DashboardClient — thin REST client for the Tata dashboard bridge API.
 *
 * Wraps the `/api/v1/agent/*` endpoints (Phase 5) plus `/auth/login`. The
 * extension stores the access token in VS Code SecretStorage; this client just
 * attaches it as a Bearer token. It never manages tickets — bridge only.
 */

export interface TaskRun {
  id: string;
  bundle_id: string;
  task_key: string;
  title: string;
  category: string;
  state: string;
  priority: string;
  depends_on: string[];
  workspace_id?: string | null;
}

export interface SyncResult {
  run: TaskRun;
  logs: Array<Record<string, unknown>>;
}

/** A single OpenSpec document of the task's bundle. */
export interface SpecDocument {
  title: string;
  content: string;
  data: Record<string, unknown>;
}

/** Context returned by `GET /agent/tasks/{id}/context`. */
export interface TaskContext {
  run: TaskRun;
  documents: Record<string, SpecDocument>;
}

/** A persisted coding-agent session. */
export interface AgentSession {
  id: string;
  run_id: string;
  status: string;
}

/** One file the agent wrote during an attempt. */
export interface AttemptFile {
  path: string;
  action: string;
}

export class DashboardClient {
  constructor(
    private readonly baseUrl: string,
    private token: string | undefined,
    private readonly workspaceId?: string,
  ) {}

  setToken(token: string | undefined): void {
    this.token = token;
  }

  private headers(json = true): Record<string, string> {
    const h: Record<string, string> = {};
    if (json) {
      h["Content-Type"] = "application/json";
    }
    if (this.token) {
      h["Authorization"] = `Bearer ${this.token}`;
    }
    if (this.workspaceId) {
      h["X-Workspace-Id"] = this.workspaceId;
    }
    return h;
  }

  private url(path: string): string {
    return `${this.baseUrl.replace(/\/$/, "")}${path}`;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T | null> {
    const res = await fetch(this.url(path), {
      method,
      headers: this.headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (res.status === 204) {
      return null;
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${method} ${path} failed: ${res.status} ${text}`);
    }
    return (await res.json()) as T;
  }

  // -- auth ---------------------------------------------------------------
  async login(email: string, password: string): Promise<string> {
    const data = await this.request<{ access_token: string }>(
      "POST",
      "/api/v1/auth/login",
      { email, password },
    );
    if (!data?.access_token) {
      throw new Error("Login response did not include an access_token");
    }
    return data.access_token;
  }

  // -- pull ---------------------------------------------------------------
  async pullNext(categories: string[]): Promise<TaskRun | null> {
    return this.request<TaskRun>("POST", "/api/v1/agent/tasks/next", {
      categories: categories.length ? categories : null,
    });
  }

  // -- push ---------------------------------------------------------------
  pushProgress(runId: string, percent: number, message: string): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/progress`, {
      percent,
      message,
    });
  }

  pushLog(runId: string, level: string, message: string): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/log`, { level, message });
  }

  pushCommit(runId: string, sha: string, message: string, branch?: string): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/commit`, {
      sha,
      message,
      branch,
    });
  }

  pushReview(runId: string, status: string, summary: string): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/review`, { status, summary });
  }

  pushError(runId: string, message: string, retry: boolean): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/error`, { message, retry });
  }

  complete(runId: string, summary: string, result: Record<string, unknown>): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/tasks/${runId}/complete`, { summary, result });
  }

  // -- sync ---------------------------------------------------------------
  async sync(runId: string): Promise<SyncResult> {
    const data = await this.request<SyncResult>("GET", `/api/v1/agent/tasks/${runId}`);
    if (!data) {
      throw new Error("Sync returned no data");
    }
    return data;
  }

  // -- coding agent (Phase 6) ---------------------------------------------
  async getContext(runId: string): Promise<TaskContext> {
    const data = await this.request<TaskContext>(
      "GET",
      `/api/v1/agent/tasks/${runId}/context`,
    );
    if (!data) {
      throw new Error("Context returned no data");
    }
    return data;
  }

  async startSession(runId: string): Promise<AgentSession> {
    const data = await this.request<AgentSession>(
      "POST",
      `/api/v1/agent/tasks/${runId}/agent/session`,
      {},
    );
    if (!data) {
      throw new Error("startSession returned no data");
    }
    return data;
  }

  recordPlan(sessionId: string, plan: Record<string, unknown>): Promise<unknown> {
    return this.request("POST", `/api/v1/agent/agent/sessions/${sessionId}/plan`, {
      plan,
    });
  }

  recordAttempt(
    sessionId: string,
    attempt: {
      iteration: number;
      phase: string;
      status: string;
      compile_output?: string;
      files?: AttemptFile[];
      error?: string | null;
    },
  ): Promise<unknown> {
    return this.request(
      "POST",
      `/api/v1/agent/agent/sessions/${sessionId}/attempt`,
      attempt,
    );
  }

  finishSession(sessionId: string, status: string, summary: string): Promise<unknown> {
    return this.request(
      "POST",
      `/api/v1/agent/agent/sessions/${sessionId}/finish`,
      { status, summary },
    );
  }
}
