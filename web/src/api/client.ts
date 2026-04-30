import type {
  ActiveProject,
  AppSettings,
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
  UpdateCheckInfo,
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

// Update check
export const checkForUpdate = () => fetchJson<UpdateCheckInfo>("/api/update-check");

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

export const createProject = (name: string, path?: string) =>
  fetchJson<ProjectEntry>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, path }),
  });

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
