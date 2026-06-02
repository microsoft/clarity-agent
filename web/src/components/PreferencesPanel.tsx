import React, { useCallback, useEffect, useState } from "react";
import {
  getSettings,
  updateSettings,
  getSetupProviders,
  configureProvider,
  testConnection,
  activateProvider,
} from "../api/client";
import type { AppSettings, ProviderInfo, AuthModeInfo } from "../types";
import { openExternalUrl } from "../data/externalLinks";
import ProviderFieldList from "./ProviderFieldList";

type Tab = "provider" | "models" | "appearance" | "accessibility";

interface PreferencesPanelProps {
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Tab: Provider
// ---------------------------------------------------------------------------

/** Animated disclosure: smoothly grows/shrinks to fit children. */
function Expandable({ open, children }: { open: boolean; children: React.ReactNode }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [height, setHeight] = React.useState<number | undefined>(open ? undefined : 0);

  React.useEffect(() => {
    if (!ref.current) return;
    if (open) {
      // Measure natural height then animate to it.
      const h = ref.current.scrollHeight;
      setHeight(h);
      const id = setTimeout(() => setHeight(undefined), 200); // after transition, allow auto
      return () => clearTimeout(id);
    } else {
      // Snap to current height then animate to 0.
      setHeight(ref.current.scrollHeight);
      requestAnimationFrame(() => setHeight(0));
    }
  }, [open]);

  return (
    <div
      ref={ref}
      style={{ height: height !== undefined ? height : undefined, overflow: "hidden" }}
      className="transition-[height] duration-200 ease-in-out"
    >
      {children}
    </div>
  );
}

function ProviderTab({ settings, onSaved }: { settings: AppSettings; onSaved: () => void }) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selected, setSelected] = useState<ProviderInfo | null>(null);
  const [selectedMode, setSelectedMode] = useState<AuthModeInfo | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string; hint?: string } | null>(null);

  useEffect(() => {
    getSetupProviders().then((r) => {
      setProviders(r.providers);
      if (settings.provider) {
        const current = r.providers.find((p) => p.name === settings.provider);
        if (current) {
          setSelected(current);
          if (settings.auth_mode) {
            const mode = current.auth_modes.find((m) => m.name === settings.auth_mode);
            if (mode) setSelectedMode(mode);
          } else if (current.auth_modes.length === 1) {
            setSelectedMode(current.auth_modes[0]);
          }
        }
      }
    });
  }, [settings.provider, settings.auth_mode]);

  // Determine which providers are configured (have stored credentials).
  const isConfigured = (provName: string): boolean => {
    // Has a remembered auth mode from a previous configuration?
    if (settings.provider_auth_modes[provName]) return true;
    // Legacy check: provider-specific credential flags.
    switch (provName) {
      case "anthropic": return settings.has_anthropic_key;
      case "openai": return settings.has_openai_key;
      case "azure": return settings.has_azure_key || settings.has_azure_endpoint;
      default: return false;
    }
  };

  const handleSelectProvider = (p: ProviderInfo) => {
    if (selected?.name === p.name) {
      setSelected(null);
      setSelectedMode(null);
    } else {
      setSelected(p);
      setSelectedMode(null);
      if (p.auth_modes.length === 1) {
        setSelectedMode(p.auth_modes[0]);
      }
    }
    setCredentials({});
    setResult(null);
  };

  const handleSelectMode = (mode: AuthModeInfo) => {
    if (selectedMode?.name === mode.name) {
      setSelectedMode(null);
    } else {
      setSelectedMode(mode);
    }
    setCredentials({});
    setResult(null);
  };

  /** One-click switch to a previously configured provider. */
  const handleSwitch = async (provName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Don't toggle the card open/closed.
    const authMode = settings.provider_auth_modes[provName];
    if (!authMode) return;
    setSwitching(true);
    try {
      await activateProvider(provName, authMode);
      onSaved();
    } catch {
      // Silently fail — the user can expand and reconfigure.
    } finally {
      setSwitching(false);
    }
  };

  const handleTest = async () => {
    if (!selected || !selectedMode) return;
    setTesting(true);
    setResult(null);
    try {
      const r = await testConnection(selected.name, selectedMode.name, credentials);
      setResult(r);
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!selected || !selectedMode) return;
    setSaving(true);
    try {
      const r = await configureProvider(selected.name, selectedMode.name, credentials);
      if (r.ok) {
        setResult({ ok: true, message: "Configuration saved." });
        onSaved();
      } else {
        setResult(r);
      }
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  // All fields (common + mode-specific) must be filled for test.
  const allFields = [
    ...(selected?.common_fields ?? []),
    ...(selectedMode?.fields ?? []),
  ];
  const canTest =
    selected && selectedMode &&
    allFields.every((f) => f.optional || credentials[f.key]?.trim());

  const isActive = (provName: string, modeName?: string) =>
    provName === settings.provider && (!modeName || modeName === settings.auth_mode);

  return (
    <div className="space-y-2">
      {providers.map((p) => {
        const provOpen = selected?.name === p.name;
        const active = isActive(p.name);
        const configured = isConfigured(p.name);

        return (
          <div
            key={p.name}
            className={`rounded-lg border transition-colors duration-200
              ${active
                ? "border-accent-focus/60 bg-accent-focus/5"
                : provOpen
                  ? "border-accent-focus bg-accent-focus/5"
                  : "border-border bg-surface hover:border-accent/40"
              }`}
          >
            {/* Provider header — always visible */}
            <button
              onClick={() => handleSelectProvider(p)}
              className="w-full text-left p-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {/* Status indicator: only the active provider gets a checkmark. */}
                  {active ? (
                    <span className="w-4 h-4 rounded-full bg-accent-focus flex items-center justify-center flex-shrink-0">
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </span>
                  ) : (
                    <span className="w-4 h-4 rounded-full border-2 border-border flex-shrink-0" />
                  )}
                  <span className="font-medium text-sm text-body-heading">{p.display_name}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {configured && !active && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-dim text-body-muted font-medium">
                      Configured
                    </span>
                  )}
                  {/* Quick-switch for configured-but-not-active providers */}
                  {configured && !active && settings.provider_auth_modes[p.name] && (
                    <button
                      onClick={(e) => handleSwitch(p.name, e)}
                      disabled={switching}
                      className="text-[10px] px-2 py-0.5 rounded bg-accent-focus/10 text-accent-focus font-medium
                        hover:bg-accent-focus/20 transition-colors disabled:opacity-50"
                    >
                      Use this
                    </button>
                  )}
                  {active && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-focus/15 text-accent-focus font-medium">
                      Active
                    </span>
                  )}
                  <svg
                    className={`w-4 h-4 text-body-faint transition-transform duration-200
                      ${provOpen ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </div>
              </div>
              <div className="text-xs text-body-muted mt-0.5 ml-6">{p.description}</div>
            </button>

            {/* Expanded provider body */}
            <Expandable open={provOpen}>
              <div className="px-3 pb-3 space-y-3">
                {/* Common fields (e.g. Azure endpoint) */}
                {p.common_fields && p.common_fields.length > 0 && (
                  <div className="space-y-2 pt-1">
                    <ProviderFieldList fields={p.common_fields} credentials={credentials} onChange={setCredentials} />
                  </div>
                )}

                {/* Auth mode cards (skip for single-mode providers) */}
                {p.auth_modes.length > 1 && (
                  <div className="space-y-1.5">
                    <p className="text-[11px] text-body-faint font-medium uppercase tracking-wide">
                      Sign-in method
                    </p>
                    {p.auth_modes.map((mode, i) => {
                      const modeOpen = selectedMode?.name === mode.name;
                      const modeActive = isActive(p.name, mode.name);

                      return (
                        <div
                          key={mode.name}
                          className={`rounded-md border transition-colors duration-200
                            ${!mode.available
                              ? "border-border/50 opacity-50"
                              : modeOpen
                                ? "border-accent-focus/60 bg-accent-focus/5"
                                : "border-border bg-surface hover:border-accent/40"
                            }`}
                        >
                          {/* Mode header */}
                          <button
                            onClick={() => handleSelectMode(mode)}
                            className="w-full text-left px-2.5 py-2"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-body-heading">{mode.display_name}</span>
                              <div className="flex items-center gap-1.5">
                                {i === 0 && mode.available && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-focus/15 text-accent-focus font-medium">
                                    Recommended
                                  </span>
                                )}
                                {modeActive && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 font-medium">
                                    Active
                                  </span>
                                )}
                                {!mode.available && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-dim text-body-faint font-medium">
                                    Not installed
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="text-xs text-body-muted mt-0.5">{mode.description}</div>
                          </button>

                          {/* Expanded mode body */}
                          <Expandable open={modeOpen}>
                            <div className="px-2.5 pb-2.5 space-y-2">
                              {mode.setup_help && (
                                <p className="text-xs text-body-muted leading-relaxed">
                                  {mode.setup_help}
                                  {mode.setup_url && (
                                    <>
                                      {" "}
                                      <a
                                        href={mode.setup_url}
                                        onClick={(event) => openExternalUrl(mode.setup_url!, event)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-accent-focus hover:underline">
                                        Open dashboard &rarr;
                                      </a>
                                    </>
                                  )}
                                </p>
                              )}
                              {mode.fields.length > 0 && (
                                <ProviderFieldList fields={mode.fields} credentials={credentials} onChange={setCredentials} />
                              )}
                            </div>
                          </Expandable>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Single-mode: show setup help + mode-specific fields inline */}
                {p.auth_modes.length === 1 && selectedMode && (
                  <>
                    {selectedMode.setup_help && (
                      <p className="text-xs text-body-muted leading-relaxed">
                        {selectedMode.setup_help}
                        {selectedMode.setup_url && (
                          <>
                            {" "}
                            <a
                              href={selectedMode.setup_url}
                              onClick={(event) => openExternalUrl(selectedMode.setup_url!, event)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-accent-focus hover:underline">
                              Open dashboard &rarr;
                            </a>
                          </>
                        )}
                      </p>
                    )}
                    {selectedMode.fields.length > 0 && (
                      <ProviderFieldList fields={selectedMode.fields} credentials={credentials} onChange={setCredentials} />
                    )}
                  </>
                )}

                {/* Actions: test + save (or switch for zero-field modes) */}
                {selectedMode && (
                  <div className="space-y-2 pt-1">
                    {allFields.length > 0 ? (
                      <div className="flex gap-2">
                        <button
                          onClick={handleTest}
                          disabled={!canTest || testing}
                          className="px-3 py-2 rounded-lg border border-border text-sm text-body-label
                            hover:bg-surface-dim disabled:opacity-40 transition-all"
                        >
                          {testing ? "Testing..." : "Test Connection"}
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={!canTest || saving}
                          className="px-3 py-2 rounded-lg bg-accent-focus text-white text-sm
                            hover:brightness-110 disabled:opacity-40 transition-all"
                        >
                          {saving ? "Saving..." : "Save"}
                        </button>
                      </div>
                    ) : !isActive(p.name, selectedMode.name) ? (
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="px-3 py-2 rounded-lg bg-accent-focus text-white text-sm
                          hover:brightness-110 disabled:opacity-40 transition-all"
                      >
                        {saving ? "Saving..." : `Switch to ${selectedMode.display_name}`}
                      </button>
                    ) : null}

                    {/* Package not installed hint */}
                    {!selectedMode.available && (
                      <p className="text-xs text-status-warn-text bg-status-warn-bg rounded-lg px-3 py-2">
                        The required package is not installed yet. You can save
                        your credentials now and install the package later.
                      </p>
                    )}

                    {/* Test result */}
                    {result && (
                      <div className={`p-2.5 rounded-lg border text-sm ${
                        result.ok
                          ? "bg-green-500/5 border-green-500/20 text-green-400"
                          : "bg-red-500/5 border-red-500/20 text-red-400"
                      }`}>
                        {result.ok ? "\u2713" : "\u2717"} {result.message}
                        {result.hint && <p className="text-xs mt-1 opacity-80">{result.hint}</p>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Expandable>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Models
// ---------------------------------------------------------------------------

function ModelsTab({ settings, onSaved }: { settings: AppSettings; onSaved: () => void }) {
  const [modelDefault, setModelDefault] = useState(settings.model_default ?? "");
  const [modelDeep, setModelDeep] = useState(settings.model_deep ?? "");
  const [modelFast, setModelFast] = useState(settings.model_fast ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    await updateSettings({
      model_default: modelDefault || null,
      model_deep: modelDeep || null,
      model_fast: modelFast || null,
    });
    setSaving(false);
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 2000);
  };

  const tiers = [
    { key: "model_default", label: "Default", sublabel: "Used for most processes", value: modelDefault, set: setModelDefault },
    { key: "model_deep", label: "Deep", sublabel: "For complex reasoning (architecture, decisions)", value: modelDeep, set: setModelDeep },
    { key: "model_fast", label: "Fast", sublabel: "For quick tasks (thinker runs, routing)", value: modelFast, set: setModelFast },
  ];

  return (
    <div className="space-y-4">
      <p className="text-xs text-body-muted">
        Override the default model for each tier. Leave blank to use the provider's default.
      </p>

      {tiers.map((t) => (
        <div key={t.key}>
          <label className="block text-xs text-body-label mb-1">
            {t.label}
            <span className="text-body-faint ml-1.5 font-normal">{t.sublabel}</span>
          </label>
          <input
            type="text"
            placeholder="Provider default"
            value={t.value}
            onChange={(e) => t.set(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface-ground
              text-sm text-body-heading placeholder:text-body-faint
              focus:outline-none focus:border-accent-focus focus:ring-1 focus:ring-accent-focus/30
              transition-all"
          />
        </div>
      ))}

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-2 rounded-lg bg-accent-focus text-white text-sm
            hover:brightness-110 disabled:opacity-50 transition-all"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        {saved && <span className="text-xs text-green-400">{"\u2713"} Saved</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Appearance
// ---------------------------------------------------------------------------

const THEMES = [
  {
    id: "sage",
    name: "Sage",
    description: "Dark emerald with warm stone surfaces",
    swatch: ["#064e3b", "#78716c", "#f5f5f4"],
  },
  {
    id: "researcher",
    name: "Researcher",
    description: "Deep ink with warm cream surfaces",
    swatch: ["#1e293b", "#d97706", "#fffbeb"],
  },
  {
    id: "high-contrast",
    name: "High Contrast",
    description: "Maximum readability, AAA contrast, color-blind safe",
    swatch: ["#000000", "#0046a0", "#ffffff"],
  },
];

function AppearanceTab({ settings, onSaved }: { settings: AppSettings; onSaved: () => void }) {
  const [theme, setTheme] = useState(settings.theme);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSelect = async (id: string) => {
    setTheme(id);
    // Apply immediately for preview.
    document.documentElement.setAttribute("data-theme", id);
    setSaving(true);
    setSaved(false);
    await updateSettings({ theme: id });
    setSaving(false);
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-body-muted">Choose a visual theme.</p>

      <div className="grid grid-cols-2 gap-3">
        {THEMES.map((t) => (
          <button
            key={t.id}
            onClick={() => handleSelect(t.id)}
            disabled={saving}
            className={`p-3 rounded-lg border text-left transition-all duration-150
              ${theme === t.id
                ? "border-accent-focus bg-accent-focus/5"
                : "border-border bg-surface hover:border-accent/40"
              }`}
          >
            {/* Color swatch */}
            <div className="flex gap-1 mb-2">
              {t.swatch.map((color, i) => (
                <div
                  key={i}
                  className="w-5 h-5 rounded-full border border-white/10"
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <div className="text-sm font-medium text-body-heading">{t.name}</div>
            <div className="text-[11px] text-body-muted mt-0.5">{t.description}</div>
          </button>
        ))}
      </div>

      {saved && <span className="text-xs text-green-400">{"\u2713"} Theme applied</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Accessibility
// ---------------------------------------------------------------------------

const FONT_SCALE_PRESETS = [
  { value: 100, label: "Default" },
  { value: 125, label: "Large" },
  { value: 150, label: "Extra Large" },
];

const MOTION_OPTIONS = [
  { value: "system", label: "Follow system setting" },
  { value: "reduce", label: "Always reduce motion" },
  { value: "no-preference", label: "Always show animations" },
];

function applyAccessibilitySettings(fontScale: number, reduceMotion: string) {
  document.documentElement.style.setProperty("--font-scale", String(fontScale / 100));
  document.documentElement.setAttribute("data-reduce-motion", reduceMotion);
}

function AccessibilityTab({ settings, onSaved }: { settings: AppSettings; onSaved: () => void }) {
  const [fontScale, setFontScale] = useState(settings.font_scale);
  const [reduceMotion, setReduceMotion] = useState(settings.reduce_motion);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    await updateSettings({ font_scale: fontScale, reduce_motion: reduceMotion });
    applyAccessibilitySettings(fontScale, reduceMotion);
    setSaving(false);
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 2000);
  };

  // Live preview while adjusting.
  const handleFontScaleChange = (value: number) => {
    setFontScale(value);
    document.documentElement.style.setProperty("--font-scale", String(value / 100));
  };

  return (
    <div className="space-y-5">
      {/* Font size */}
      <div>
        <label className="block text-xs text-body-label mb-2">
          Font size
          <span className="text-body-faint ml-1.5 font-normal">{fontScale}%</span>
        </label>
        <input
          type="range"
          min={75}
          max={200}
          step={5}
          value={fontScale}
          onChange={(e) => handleFontScaleChange(parseInt(e.target.value))}
          className="w-full accent-accent-focus"
          aria-label={`Font size: ${fontScale}%`}
        />
        <div className="flex justify-between mt-1.5">
          {FONT_SCALE_PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => handleFontScaleChange(p.value)}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                fontScale === p.value
                  ? "bg-accent-focus/15 text-accent-focus font-medium"
                  : "text-body-muted hover:text-body-heading"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Reduce motion */}
      <fieldset>
        <legend className="text-xs text-body-label mb-2">
          Motion &amp; animations
        </legend>
        <div className="space-y-1.5">
          {MOTION_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="reduce-motion"
                value={opt.value}
                checked={reduceMotion === opt.value}
                onChange={() => setReduceMotion(opt.value)}
                className="text-accent-focus focus:ring-accent-focus/30"
              />
              <span className="text-sm text-body-heading">{opt.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Keyboard shortcuts */}
      <div>
        <p className="text-xs text-body-label mb-2">Keyboard shortcuts</p>
        <div className="rounded-lg border border-border bg-surface-ground px-3 py-2.5 space-y-1.5">
          {[
            ["Enter", "Send message"],
            ["Shift + Enter", "New line in message"],
            ["Tab", "Move focus to next element"],
            ["Escape", "Close dialog / cancel"],
          ].map(([key, desc]) => (
            <div key={key} className="flex items-center justify-between text-xs">
              <span className="text-body-muted">{desc}</span>
              <kbd className="px-1.5 py-0.5 rounded bg-surface-muted text-body-label font-mono text-[11px]">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </div>

      {/* High contrast hint */}
      <p className="text-xs text-body-faint leading-relaxed">
        For maximum contrast, select the High Contrast theme in the
        Appearance tab.
      </p>

      {/* Save */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-2 rounded-lg bg-accent-focus text-white text-sm
            hover:brightness-110 disabled:opacity-50 transition-all"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        {saved && <span className="text-xs text-green-400">{"\u2713"} Saved</span>}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function PreferencesPanel({ onClose }: PreferencesPanelProps) {
  const [tab, setTab] = useState<Tab>("provider");
  const [settings, setSettings] = useState<AppSettings | null>(null);

  const loadSettings = useCallback(() => {
    getSettings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  if (!settings) return null;

  const tabs: { id: Tab; label: string }[] = [
    { id: "provider", label: "Provider" },
    { id: "models", label: "Models" },
    { id: "appearance", label: "Appearance" },
    { id: "accessibility", label: "Accessibility" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-surface rounded-xl shadow-2xl w-full max-w-lg mx-4 min-h-[28rem] max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
          <h2 className="text-lg font-display text-body-heading">Preferences</h2>
          <button
            onClick={onClose}
            aria-label="Close preferences"
            className="p-1 text-body-faint hover:text-body-muted transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-border px-6">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-2.5 text-sm transition-colors relative
                ${tab === t.id
                  ? "text-accent-focus"
                  : "text-body-muted hover:text-body-heading"
                }`}
            >
              {t.label}
              {tab === t.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-focus rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {tab === "provider" && <ProviderTab settings={settings} onSaved={loadSettings} />}
          {tab === "models" && <ModelsTab settings={settings} onSaved={loadSettings} />}
          {tab === "appearance" && <AppearanceTab settings={settings} onSaved={loadSettings} />}
          {tab === "accessibility" && <AccessibilityTab settings={settings} onSaved={loadSettings} />}
        </div>
      </div>
    </div>
  );
}
