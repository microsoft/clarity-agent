import { useCallback, useEffect, useRef, useState } from "react";
import { activateProvider, getModels, getSettings, getSession, setModel as putModel } from "../api/client";
import type { ModelCatalogInfo, ModelEntry, SessionInfo, AppSettings } from "../types";
import { useChat } from "../hooks/useChat";

// Labels for the highlighted models a provider names.  "default" is
// the model we run unless the user picks otherwise; the other two are
// the heavier and lighter options offered beside it.
const ROLE_LABELS: Record<string, string> = {
  default: "Recommended",
  deep: "Deeper thinking",
  fast: "Faster",
};

// Short display names for providers.
const PROVIDER_NAMES: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  azure: "Azure AI",
  gemini: "Gemini",
  github: "GitHub Copilot",
};

function providerLabel(provider: string): string {
  return PROVIDER_NAMES[provider] ?? provider;
}

function formatContext(tokens: number | null): string | null {
  if (!tokens) return null;
  if (tokens >= 1_000_000) {
    const millions = tokens / 1_000_000;
    return `${Number.isInteger(millions) ? millions : millions.toFixed(1)}M context`;
  }
  return `${Math.round(tokens / 1000)}K context`;
}

export default function ModelSelector() {
  const { activeModel, setModel } = useChat();
  const [catalog, setCatalog] = useState<ModelCatalogInfo | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [typed, setTyped] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const loadCatalog = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const next = await getModels(refresh);
      setCatalog(next);
      setTyped(next.current);
    } catch {
      // Leave whatever we had; the collapsed row still shows the
      // active model, which comes from the session, not from here.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
    getSession().then(setSession).catch(() => {});
    getSettings().then((s: AppSettings) => {
      setConfiguredProviders(s.provider_auth_modes ?? {});
    }).catch(() => {});
  }, [loadCatalog]);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleSelect = useCallback(
    async (modelId: string) => {
      const id = modelId.trim();
      if (!id) return;
      setOpen(false);
      // Tell the live socket first so the running session switches
      // immediately, then persist so the choice outlives this session.
      setModel(id);
      setCatalog((prev) => (prev ? { ...prev, current: id } : prev));
      try {
        await putModel(id);
      } catch {
        // The socket already applied it to this session; a failed
        // write just means it won't be remembered next time.
      }
    },
    [setModel],
  );

  const handleSwitchProvider = useCallback(
    async (provName: string) => {
      const authMode = configuredProviders[provName];
      if (!authMode) return;
      setSwitching(true);
      setOpen(false);
      try {
        await activateProvider(provName, authMode);
        window.location.reload();
      } catch {
        setSwitching(false);
      }
    },
    [configuredProviders],
  );

  const currentProvider = session?.backend ?? "";
  const currentModel = activeModel ?? catalog?.current ?? "";
  const allProviders = Object.keys(configuredProviders);

  const highlighted = (catalog?.models ?? []).filter((m) => m.role);
  const rest = (catalog?.models ?? []).filter((m) => !m.role);

  const currentEntry = catalog?.models.find((m) => m.id === currentModel);
  const currentLabel = currentEntry?.display_name ?? currentModel;

  const renderModel = (model: ModelEntry) => {
    const isSelected = model.id === currentModel;
    const context = formatContext(model.context_window);
    return (
      <button
        key={model.id}
        onClick={() => handleSelect(model.id)}
        className={`w-full text-left px-4 py-2.5 text-xs transition-all duration-150 ${
          isSelected
            ? "bg-sidebar-active text-sidebar-text"
            : "text-sidebar-text-muted hover:bg-sidebar-active/60 hover:text-sidebar-text"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium truncate">{model.display_name}</span>
          {model.role && (
            <span className="text-[10px] text-sidebar-text-faint flex-shrink-0 uppercase tracking-wider">
              {ROLE_LABELS[model.role] ?? model.role}
            </span>
          )}
        </div>
        <div
          className="font-mono text-sidebar-text-faint truncate mt-0.5"
          style={{ fontSize: "0.6rem" }}
          title={model.id}
        >
          {model.id}
          {context ? ` · ${context}` : ""}
        </div>
      </button>
    );
  };

  return (
    <div ref={ref} className="relative">
      {/* Collapsed: provider and the model actually in use */}
      <button
        onClick={() => setOpen(!open)}
        aria-label="Model and provider selector"
        className="w-full text-left px-5 py-3.5 border-t border-sidebar-line/30
                   text-xs transition-all duration-200 group"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="min-w-0">
            <span className="block text-sidebar-text-muted group-hover:text-sidebar-text-secondary transition-colors truncate">
              {currentLabel || providerLabel(currentProvider)}
            </span>
            {currentLabel && (
              <span className="block text-sidebar-text-faint truncate" style={{ fontSize: "0.6rem" }}>
                {providerLabel(currentProvider)}
              </span>
            )}
          </span>
          <svg
            className={`w-3 h-3 text-sidebar-text-faint transition-transform duration-200 flex-shrink-0 ${open ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          </svg>
        </div>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 mx-3
                        bg-sidebar border border-sidebar-line/40 rounded-xl
                        shadow-xl shadow-black/30 overflow-hidden z-50
                        animate-fade-up flex flex-col max-h-[70vh]"
             style={{ animationDuration: "0.15s" }}>

          {/* Provider section — only when more than one is configured */}
          {allProviders.length > 1 && (
            <>
              <div className="px-4 pt-2.5 pb-1.5 text-[10px] text-sidebar-text-faint uppercase tracking-wider">
                Provider
              </div>
              {allProviders.map((prov) => {
                const isCurrent = prov === currentProvider;
                return (
                  <button
                    key={prov}
                    onClick={() => !isCurrent && handleSwitchProvider(prov)}
                    disabled={switching || isCurrent}
                    className={`w-full text-left px-4 py-2 text-xs flex items-center justify-between
                      disabled:cursor-default transition-all duration-150 ${
                        isCurrent
                          ? "bg-sidebar-active text-sidebar-text"
                          : "text-sidebar-text-muted hover:bg-sidebar-active/60 hover:text-sidebar-text disabled:opacity-50"
                      }`}
                  >
                    <span>{providerLabel(prov)}</span>
                    {isCurrent && (
                      <svg className="w-3 h-3 flex-shrink-0 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                );
              })}
              <div className="border-t border-sidebar-line/20 my-1" />
            </>
          )}

          {catalog?.error && (
            <div className="px-4 py-2 text-[10px] text-sidebar-text-faint leading-relaxed">
              Couldn't reach {providerLabel(currentProvider)} for the model
              list — showing the models built into this release.
            </div>
          )}

          {/* Azure and friends: deployments are user-named, so there's
              nothing to list.  Take a typed identifier instead. */}
          {catalog?.free_form ? (
            <form
              className="p-4 space-y-2"
              onSubmit={(e) => {
                e.preventDefault();
                handleSelect(typed);
              }}
            >
              <label className="block text-[10px] text-sidebar-text-faint uppercase tracking-wider">
                Deployment name
              </label>
              <input
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="my-gpt-deployment"
                className="w-full px-2.5 py-1.5 rounded-lg bg-sidebar-active/40
                           border border-sidebar-line/40 text-xs text-sidebar-text
                           focus:outline-none focus:ring-1 focus:ring-sidebar-line"
              />
              <p className="text-[10px] text-sidebar-text-faint leading-relaxed">
                Azure deployments are named when you provision them, so
                there's no list to fetch. Any name your resource serves
                will work.
              </p>
            </form>
          ) : (
            <div className="overflow-y-auto">
              {highlighted.length > 0 && (
                <>
                  <div className="px-4 pt-2 pb-1.5 text-[10px] text-sidebar-text-faint uppercase tracking-wider">
                    Recommended
                  </div>
                  {highlighted.map(renderModel)}
                </>
              )}

              {rest.length > 0 && (
                <>
                  <div className="px-4 pt-2.5 pb-1.5 text-[10px] text-sidebar-text-faint uppercase tracking-wider border-t border-sidebar-line/20 mt-1">
                    All models
                  </div>
                  {rest.map(renderModel)}
                </>
              )}

              {!loading && (catalog?.models.length ?? 0) === 0 && (
                <div className="px-4 py-3 text-xs text-sidebar-text-faint">
                  No models available.
                </div>
              )}
            </div>
          )}

          <button
            onClick={() => loadCatalog(true)}
            disabled={loading}
            className="w-full text-left px-4 py-2 text-[10px] text-sidebar-text-faint
                       hover:text-sidebar-text-muted border-t border-sidebar-line/20
                       transition-colors disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh list"}
          </button>
        </div>
      )}
    </div>
  );
}
