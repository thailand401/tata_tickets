# Tata Agent Bridge (VS Code Extension) — Phase 5

A thin bridge between the **Tata AI Software Factory dashboard** and VS Code.
It lets a developer (or an AI coding agent running in the editor) **pull**
assigned tasks and **push** their results back to the dashboard.

> This extension is a **bridge only**. It does not create, edit, or manage
> tickets, specs, or bundles — all of that lives in the dashboard. The bridge
> simply moves a single task run through its lifecycle.

## What it does

| Capability       | Command                  | Dashboard endpoint                       |
|------------------|--------------------------|------------------------------------------|
| Login            | `Tata: Login`            | `POST /api/v1/auth/login`                |
| Pull task        | `Tata: Pull Next Task`   | `POST /api/v1/agent/tasks/next`          |
| Push progress    | `Tata: Push Progress`    | `POST /api/v1/agent/tasks/{id}/progress` |
| Push log         | `Tata: Push Log`         | `POST /api/v1/agent/tasks/{id}/log`      |
| Push commit      | `Tata: Push Commit`      | `POST /api/v1/agent/tasks/{id}/commit`   |
| Push review      | `Tata: Push Review`      | `POST /api/v1/agent/tasks/{id}/review`   |
| Push error       | `Tata: Push Error`       | `POST /api/v1/agent/tasks/{id}/error`    |
| Complete         | `Tata: Complete Task`    | `POST /api/v1/agent/tasks/{id}/complete` |
| Realtime sync    | `Tata: Sync` (+ polling) | `GET /api/v1/agent/tasks/{id}`           |

## Settings

- `tata.dashboardUrl` — base URL of the dashboard (default `http://localhost:8080`).
- `tata.categories` — task lanes this worker pulls (empty = any).
- `tata.workspaceId` — optional workspace scope.
- `tata.syncIntervalMs` — realtime polling interval.

The access token is stored in VS Code **SecretStorage** (never in settings).

## Develop

```bash
cd extension
npm install
npm run compile      # or: npm run watch
# Press F5 in VS Code to launch the Extension Development Host.
```

## Flow

1. `Tata: Login` → token saved to SecretStorage.
2. `Tata: Pull Next Task` → claims the highest-priority ready task whose
   dependencies have all succeeded; starts the realtime sync poller.
3. Work in the editor, pushing **progress / log / commit / review** as you go.
4. `Tata: Complete Task` on success, or `Tata: Push Error` (with retry choice)
   on failure — the dashboard re-queues or marks the task dead accordingly.
