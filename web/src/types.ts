// WebSocket messages: client → server
export type WsClientMessage =
  | { type: "chat"; message: string }
  | { type: "start_process"; process: string; scenario_id?: string }
  | { type: "set_model_override"; tier: string }
  | { type: "stop" };

// WebSocket messages: server → client
export type WsServerMessage =
  | { type: "tool_use"; tool: string; detail: string }
  | { type: "text_delta"; content: string }
  | { type: "cost"; cost_usd: number }
  | { type: "usage"; input_tokens: number; output_tokens: number }
  | { type: "response"; content: string }
  | { type: "model_changed"; tier: string; model: string; auto: boolean }
  | { type: "error"; message: string; category?: string; hint?: string; retryable?: boolean }
  | { type: "warning"; message: string }
  | { type: "status"; phase: string }
  | {
      type: "compaction_complete";
      /** True if the provider's own auto-compaction produced the
       *  summary; false if our threshold-based fallback ran the
       *  summarization LLM call ourselves. */
      via_backend: boolean;
      /** Which chapter was just archived. */
      source_chapter: number;
      /** Number of turns folded into the summary. */
      source_turn_count: number;
    }
  | { type: "exploration_complete" };

// Chat UI state
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  toolEvents?: ToolEvent[];
  costUsd?: number;
  /** Total tokens (input + output) for this turn. */
  tokenCount?: number;
  timestamp: number;
  /** For system messages: the process name that triggered this. */
  processName?: string;
}

export interface ToolEvent {
  tool: string;
  detail: string;
}

// Protocol tree
export interface ProtocolFile {
  path: string;
  name: string;
}

export interface ProtocolTree {
  exists: boolean;
  tree: ProtocolFile[];
}

// Packet Status
export interface DocumentStatus {
  status: "current" | "stale" | "empty" | "missing" | "untracked";
  content_hash: string | null;
  dependencies: string[];
  stale_because: { doc: string; current_hash: string; recorded_hash: string | null }[];
}

export interface PacketStatusReport {
  protocol_dir: string;
  documents: Record<string, DocumentStatus>;
  summary: {
    current: string[];
    stale: string[];
    empty: string[];
    missing: string[];
    untracked: string[];
  };
  mailboxes: { name: string; config: Record<string, unknown>; item_count: number }[];
}

export interface NextAction {
  action: string;
  document: string;
  process: string | null;
  reason: string;
}

export interface ProcessPhase {
  process: string;
  status: "recommended" | "available" | "unavailable";
  reason: string;
}

export interface PacketStatusData {
  report: PacketStatusReport;
  decisions: Record<string, unknown>;
  next_action: NextAction | null;
  process_availability: ProcessPhase[];
}

// Transcripts
export interface TranscriptEntry {
  name: string;
  modified: number;
}

// Session
export interface SessionInfo {
  active: boolean;
  /** Persistent identifier of the conversation thread for this
   *  project.  Stable across reconnects; null when no thread has
   *  been established yet. */
  thread_id: string | null;
  process: string | null;
  project_dir: string;
  project_id?: string;
  backend: string;
  model: string;
  active_model: string;
  active_tier: string;
  theme: string;
  launcher_mode?: boolean;
}

// Model profile
export interface ModelProfileInfo {
  tiers: Record<string, string>;
  override: string | null;
  auto: boolean;
  active_model: string;
  active_tier: string;
}

// Update run.  The *check* shape lives in ``VersionPayload`` —
// ``/api/version`` is now the single source of truth for both
// release-mode and git-mode update info, dispatched on
// ``latest.kind`` in the frontend.
export interface UpdateRunResult {
  steps: { outcome: string; message: string }[];
  success: boolean;
}

// Settings (preferences panel)
export interface AppSettings {
  provider: string | null;
  auth_mode: string | null;
  model_default: string | null;
  model_deep: string | null;
  model_fast: string | null;
  process_model_overrides: Record<string, string>;
  provider_auth_modes: Record<string, string>;
  theme: string;
  font_scale: number;
  reduce_motion: string;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  has_azure_key: boolean;
  has_azure_endpoint: boolean;
}

// Packets
export interface PacketSource {
  id: string;
  title: string;
}

export interface PacketPart {
  title: string;
  source_ids: string[];
}

export interface PacketView {
  id: string;
  title: string;
  description: string;
  parts: PacketPart[];
}

export interface PacketOptions {
  sources: PacketSource[];
  formats: string[];
  parts: PacketPart[];
  views: PacketView[];
  source_sizes: Record<string, number>;
}

// Setup wizard
export interface SetupStatus {
  configured: boolean;
  provider: string | null;
  has_env_file: boolean;
}

export interface ProviderField {
  key: string;
  label: string;
  secret: boolean;
  optional?: boolean;
  placeholder?: string;
  help?: string;
}

export interface AuthModeInfo {
  name: string;
  display_name: string;
  description: string;
  fields: ProviderField[];
  available: boolean;
  setup_help?: string;
  setup_url?: string;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  description: string;
  auth_modes: AuthModeInfo[];
  common_fields?: ProviderField[];
  setup_url?: string;
}

export interface ConfigureResult {
  ok: boolean;
  message: string;
  hint?: string;
}

// Projects (launcher mode)
export interface ProjectEntry {
  id: string;
  name: string;
  path: string;
  last_opened: number;
  has_protocol: boolean;
  running: boolean;
  active: boolean;
}

export interface ActiveProject {
  active: boolean;
  name?: string;
  path?: string;
  running?: boolean;
}

// Feedback
export interface FeedbackPayload {
  message: string;
  contact_ok: boolean;
  contact_email: string;
  include_llm_info: boolean;
  transcript_turns: number;
  include_protocol: boolean;
}

export interface FeedbackResult {
  submitted: boolean;
  file_path: string | null;
}

// Process metadata
export interface ProcessMeta {
  name: string;
  display_name: string;
  one_liner: string;
  tier: string;
  category: string;
}

// Onboarding (first-five-minutes exploration)
export interface OnboardingStatus {
  first_exploration_status: "not_started" | "completed" | "dismissed";
  eligible_for_auto_exploration: boolean;
  last_exploration_scenario: string | null;
  /** True when all protocol documents are still templates (no real work done). */
  project_is_fresh: boolean;
}

export interface ExplorationScenario {
  id: string;
  title: string;
  description: string;
}
