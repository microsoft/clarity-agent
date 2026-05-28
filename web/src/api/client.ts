import type {
  ActiveProject,
  AppSettings,
  ChatMessage,
  ConfigureResult,
  FeedbackPayload,
  FeedbackResult,
  ModelProfileInfo,
  PacketOptions,
  ProcessMeta,
  ProjectEntry,
  ProtocolTree,
  ProviderInfo,
  SessionInfo,
  SetupStatus,
  PacketStatusData,
  TranscriptEntry,
  UpdateRunResult,
} from "../types";

const BASE = "";

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// Protocol
export const getProtocolTree = () => fetchJson<ProtocolTree>("/api/protocol/tree");

export const getDocument = (path: string) =>
  fetchJson<{ path: string; content: string }>(`/api/protocol/document/${path}`);

// Packet Status
export const getPacketStatus = () => fetchJson<PacketStatusData>("/api/packet-status");

// Transcripts
export const getTranscripts = () =>
  fetchJson<{ transcripts: TranscriptEntry[] }>("/api/transcripts");

export const getTranscript = (name: string) =>
  fetchJson<{ name: string; content: string }>(`/api/transcripts/${name}`);

// Packets
export const getPacketOptions = () => fetchJson<PacketOptions>("/api/packet/options");

export async function generatePacket(
  sections: string[] | null,
  format: string,
  view: string | null = null,
): Promise<Blob> {
  const res = await fetch(`${BASE}/api/packet/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sections, format, view }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.blob();
}

// Session
export const getSession = () => fetchJson<SessionInfo>("/api/session");

/**
 * The running binary's version + cached update-check result.
 *
 * Mirrors the dict shape returned by
 * ``clarity_agent.web.version_endpoint.get_version_payload``.  Kept
 * in sync with that module — every field below has a counterpart
 * there.  ``version`` is a release tag (e.g. ``"v1.2.3"``) or the
 * literal ``"local"``.
 *
 * ``latest`` is a discriminated union: ``kind: "release"`` for
 * release-binary builds (links to the GitHub release page), or
 * ``kind: "git"`` for source-checkout builds (a "5 commits behind
 * <branch>" badge).  Frontends should ``switch (latest.kind)``
 * rather than re-derive the mode from ``source``.
 */
export interface ReleaseLatest {
  kind: "release";
  version: string;
  assets: Record<string, string>;
  release_url: string;
}

export interface GitLatest {
  kind: "git";
  branch: string;
  commit_count: number;
  remote_sha: string;
}

export interface VersionPayload {
  version: string;
  source: "release" | "local";
  is_release: boolean;
  // Local-mode introspection — populated only when source === "local".
  // Used by the sidebar's version label to render "<branch> @ <sha>"
  // instead of the generic "local" string.  Either field may be null
  // even in local mode if the git lookup failed (no .git/, no git
  // binary, detached HEAD) — the UI falls back to "local" then.
  branch: string | null;
  local_sha: string | null;
  update_status: "available" | "up_to_date" | "unknown";
  latest: ReleaseLatest | GitLatest | null;
  reason: string | null;
}

export const getVersion = () => fetchJson<VersionPayload>("/api/version");

// Conversation thread
/**
 * Roll the current project's conversation thread over to a new chapter.
 * The current chapter is archived (still browsable via History) and
 * the next user message starts a fresh SDK conversation with no
 * carried-over context.  Returns the new chapter number.
 */
export const startNewChapter = () =>
  fetchJson<{ chapter: number }>("/api/thread/new-chapter", { method: "POST" });

/**
 * Fetch the current chapter's prior turns as chat messages.
 * Used at mount to populate the chat panel with continuity from
 * the user's earlier conversation; the empty-list response means
 * "fresh project or fresh chapter, nothing prior to show."
 */
export const getCurrentChapter = () =>
  fetchJson<{ messages: ChatMessage[] }>("/api/thread/current-chapter");

// Update apply.  The *check* shape lives on ``getVersion()`` —
// ``/api/version`` returns ``update_status`` + a discriminated
// ``latest`` (release vs. git) that UpdateBadge dispatches on.
export const runUpdate = () =>
  fetchJson<UpdateRunResult>("/api/update/run", { method: "POST" });

export const restartServer = () =>
  fetchJson<{ restarting: boolean }>("/api/update/restart", { method: "POST" });

// Model profile
export const getModelProfile = () => fetchJson<ModelProfileInfo>("/api/model-profile");

export const setModelOverride = (tier: string) =>
  fetchJson<ModelProfileInfo>("/api/model-profile/override", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tier }),
  });

// Setup wizard
export const getSetupStatus = () => fetchJson<SetupStatus>("/api/setup/status");

export const getSetupProviders = () =>
  fetchJson<{ providers: ProviderInfo[] }>("/api/setup/providers");

export const configureProvider = (
  provider: string,
  auth_mode: string,
  credentials: Record<string, string>,
) =>
  fetchJson<ConfigureResult>("/api/setup/configure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, auth_mode, credentials }),
  });

export const testConnection = (
  provider: string,
  auth_mode: string,
  credentials: Record<string, string>,
) =>
  fetchJson<ConfigureResult>("/api/setup/test-connection", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, auth_mode, credentials }),
  });

// Process metadata
export const getProcesses = () =>
  fetchJson<{ processes: ProcessMeta[] }>("/api/processes");

// Projects (launcher mode)
export const getProjects = () =>
  fetchJson<{ projects: ProjectEntry[] }>("/api/projects");

/**
 * Discriminated union of outcomes from ``POST /api/projects``.  The
 * server returns one of these shapes; the UI dispatches on
 * ``status`` to drive flow-2 (registered + activated), the flow-3
 * SetupPromptDialog (needs_setup / broken_install), or the
 * EmbeddedCommandDialog (embedded_install_required).
 *
 * Keep these field names in sync with
 * ``src/clarity_agent/web/launcher.py``'s ``create_project`` handler.
 */
export type CreateProjectResult =
  | { status: "ok"; entry: ProjectEntry }
  | {
      status: "needs_setup";
      looks_like_code: boolean;
      suggested_mode: "embedded" | "userspace";
      path: string;
    }
  | { status: "broken_install"; brokenness: string; path: string }
  | { status: "embedded_install_required"; command: string; path: string };

// Set of recognized status discriminators, kept next to the union
// so the runtime guard below can't drift from the type.  Name
// collisions are NOT a status — the registry is path-keyed and
// allows duplicate display names; same-path reopens come back as
// "ok".
const KNOWN_CREATE_PROJECT_STATUSES = new Set([
  "ok",
  "needs_setup",
  "broken_install",
  "embedded_install_required",
]);

/**
 * Register / set up a project.  See the server-side docstring on
 * ``create_project`` for the per-(intent, mode, disk-state)
 * behavior matrix.  This wrapper handles the 409 responses
 * structurally (they carry actionable JSON, not error text), so
 * callers can ``switch`` on ``status`` rather than parsing
 * exception strings.
 */
export async function createProject(args: {
  name: string;
  path?: string;
  intent: "create_new" | "open_existing";
  mode?: "userspace" | "embedded";
}): Promise<CreateProjectResult> {
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });
  // The launcher returns 409 with structured bodies whose
  // ``status`` field discriminates the case (broken_install,
  // needs_setup, name_conflict, …).  Anything else — 4xx without
  // a recognised status, 5xx, network — throws so the caller's
  // catch block surfaces it instead of the UI silently swallowing
  // a body it doesn't understand.
  if (res.status === 200 || res.status === 409) {
    const body = await res.json();
    if (res.status === 200 && !body.status) {
      // Legacy code path that didn't set ``status`` — treat as ok.
      return { status: "ok", entry: body as ProjectEntry };
    }
    if (body.status === "ok") {
      const { status: _s, ...entry } = body;
      return { status: "ok", entry: entry as ProjectEntry };
    }
    if (KNOWN_CREATE_PROJECT_STATUSES.has(body?.status)) {
      return body as CreateProjectResult;
    }
    // Unrecognised body — most often FastAPI's ``{"detail": ...}``
    // from a bare ``HTTPException``.  Throw with the most useful
    // string we can pull out so the caller's catch surfaces it.
    const reason = body?.detail || body?.message || JSON.stringify(body);
    throw new Error(`${res.status}: ${reason}`);
  }
  const errorBody = await res.text();
  throw new Error(`${res.status}: ${errorBody}`);
}

export const removeProject = (name: string) =>
  fetchJson<{ status: string }>(`/api/projects/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });

export const activateProject = (name: string) =>
  fetchJson<{ id: string; name: string; path: string; port: number; session: SessionInfo }>(
    `/api/projects/${encodeURIComponent(name)}/activate`,
    { method: "POST" },
  );

export const activateProjectById = (id: string) =>
  fetchJson<{ id: string; name: string; path: string; port: number; session: SessionInfo }>(
    `/api/projects/activate-by-id/${encodeURIComponent(id)}`,
    { method: "POST" },
  );

export const deactivateProject = (name: string) =>
  fetchJson<{ status: string }>(
    `/api/projects/${encodeURIComponent(name)}/deactivate`,
    { method: "POST" },
  );

export const getActiveProject = () =>
  fetchJson<ActiveProject>("/api/projects/active");

// Feedback
export const sendFeedback = (payload: FeedbackPayload) =>
  fetchJson<FeedbackResult>("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

// Settings (preferences panel)
export const getSettings = () => fetchJson<AppSettings>("/api/settings");

export const activateProvider = (provider: string, auth_mode: string) =>
  fetchJson<{ ok: boolean; provider: string; auth_mode: string }>("/api/settings/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, auth_mode }),
  });

export const updateSettings = (settings: Partial<AppSettings>) =>
  fetchJson<{ ok: boolean }>("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
