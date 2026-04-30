import { useCallback, useEffect, useRef, useState } from "react";
import { activateProvider, getModelProfile, getSettings, getSession } from "../api/client";
import type { ModelProfileInfo, SessionInfo, AppSettings } from "../types";
import { useChat } from "../hooks/useChat";

// Intent-based labels and descriptions for model tiers
const TIER_DISPLAY: Record<string, { label: string; description: string }> = {
  auto: { label: "Auto", description: "Picks the best model for each step" },
  default: { label: "Balanced", description: "Good quality at reasonable cost" },
  deep: { label: "Thorough", description: "Best quality for complex reasoning" },
  fast: { label: "Quick", description: "Fastest responses, lower cost" },
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

function shortModel(model: string): string {
  return model.replace(/-\d{8}$/, "");
}

export default function ModelSelector() {
  const { activeTier, autoModel, setModelOverride } = useChat();
  const [profile, setProfile] = useState<ModelProfileInfo | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getModelProfile().then(setProfile).catch(() => {});
    getSession().then(setSession).catch(() => {});
    getSettings().then((s: AppSettings) => {
      setConfiguredProviders(s.provider_auth_modes ?? {});
    }).catch(() => {});
  }, []);

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

  const handleSelectTier = useCallback(
    (tier: string) => {
      setModelOverride(tier);
      setOpen(false);
      if (profile) {
        if (tier === "auto") {
          setProfile({ ...profile, override: null, auto: true });
        } else {
          const model = profile.tiers[tier] ?? tier;
          setProfile({
            ...profile,
            override: model,
            auto: false,
            active_model: model,
            active_tier: tier,
          });
        }
      }
    },
    [setModelOverride, profile],
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
  const displayTier = activeTier ?? profile?.active_tier ?? "default";
  const isAuto = autoModel;

  const tierOptions = ["auto", ...Object.keys(profile?.tiers ?? {})];

  // All configured providers (including the current one, which will
  // render as "checked" in the menu).
  const allProviders = Object.keys(configuredProviders);

  return (
    <div ref={ref} className="relative">
      {/* Collapsed: just the provider name */}
      <button
        onClick={() => setOpen(!open)}
        aria-label="Model and provider selector"
        className="w-full text-left px-5 py-3.5 border-t border-sidebar-line/30
                   text-xs transition-all duration-200 group"
      >
        <div className="flex items-center justify-between">
          <span className="text-sidebar-text-muted group-hover:text-sidebar-text-secondary transition-colors truncate">
            {providerLabel(currentProvider)}
          </span>
          <svg
            className={`w-3 h-3 text-sidebar-text-faint transition-transform duration-200 flex-shrink-0 ml-2 ${open ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          </svg>
        </div>
      </button>

      {/* Expanded menu */}
      {open && profile && (
        <div className="absolute bottom-full left-0 right-0 mb-1 mx-3
                        bg-sidebar border border-sidebar-line/40 rounded-xl
                        shadow-xl shadow-black/30 overflow-hidden z-50
                        animate-fade-up"
             style={{ animationDuration: "0.15s" }}>

          {/* Provider section — only shown if multiple are configured */}
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

          {/* Tier section — always show model identifiers */}
          <div className="px-4 pt-2 pb-1.5 text-[10px] text-sidebar-text-faint uppercase tracking-wider">
            {currentProvider ? providerLabel(currentProvider) : "Model tier"}
          </div>
          {tierOptions.map((tier) => {
            const isSelected =
              (tier === "auto" && isAuto) ||
              (tier !== "auto" && !isAuto && displayTier === tier);
            const model = tier === "auto" ? "" : profile.tiers[tier] ?? "";
            const display = TIER_DISPLAY[tier];

            return (
              <button
                key={tier}
                onClick={() => handleSelectTier(tier)}
                className={`w-full text-left px-4 py-2.5 text-xs transition-all duration-150 ${
                  isSelected
                    ? "bg-sidebar-active text-sidebar-text"
                    : "text-sidebar-text-muted hover:bg-sidebar-active/60 hover:text-sidebar-text"
                }`}
              >
                <div className="font-medium">
                  {display?.label ?? tier}
                </div>
                {model && (
                  <div
                    className="font-mono text-sidebar-text-faint truncate mt-0.5"
                    style={{ fontSize: "0.6rem" }}
                    title={model}
                  >
                    {shortModel(model)}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
