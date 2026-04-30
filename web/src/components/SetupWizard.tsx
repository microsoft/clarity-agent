import { useCallback, useEffect, useState } from "react";
import { getSetupProviders, configureProvider, testConnection } from "../api/client";
import type { ProviderInfo, AuthModeInfo, ProviderField } from "../types";
import ProviderFieldList from "./ProviderFieldList";

type Step = "provider" | "auth_mode" | "credentials" | "test";

interface SetupWizardProps {
  onComplete: () => void;
  onCancel?: () => void;
}

export default function SetupWizard({ onComplete, onCancel }: SetupWizardProps) {
  const [step, setStep] = useState<Step>("provider");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selected, setSelected] = useState<ProviderInfo | null>(null);
  const [selectedMode, setSelectedMode] = useState<AuthModeInfo | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; hint?: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getSetupProviders()
      .then((r) => setProviders(r.providers))
      .catch(() => {});
  }, []);

  /** True if a provider+mode combination has any fields to fill in. */
  const hasFields = (p: ProviderInfo, mode: AuthModeInfo) =>
    (p.common_fields?.length ?? 0) + mode.fields.length > 0;

  const handleSelectProvider = useCallback((p: ProviderInfo) => {
    setSelected(p);
    setSelectedMode(null);
    setCredentials({});
    setTestResult(null);

    // If only one available auth mode, auto-select it.
    const available = p.auth_modes.filter((m) => m.available);
    if (available.length === 1) {
      const mode = available[0];
      setSelectedMode(mode);
      if (hasFields(p, mode)) {
        setStep("credentials");
      } else {
        setPendingTest(true);
        setStep("test");
      }
    } else {
      setStep("auth_mode");
    }
  }, []);

  const handleSelectAuthMode = useCallback((mode: AuthModeInfo) => {
    setSelectedMode(mode);
    setCredentials({});
    setTestResult(null);
    if (selected && hasFields(selected, mode)) {
      setStep("credentials");
    } else {
      setPendingTest(true);
      setStep("test");
    }
  }, [selected]);

  const handleTest = useCallback(async () => {
    if (!selected || !selectedMode) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testConnection(selected.name, selectedMode.name, credentials);
      setTestResult(result);
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setTesting(false);
    }
  }, [selected, selectedMode, credentials]);

  const handleSave = useCallback(async () => {
    if (!selected || !selectedMode) return;
    setSaving(true);
    try {
      const result = await configureProvider(selected.name, selectedMode.name, credentials);
      if (result.ok) {
        onComplete();
      } else {
        setTestResult(result);
      }
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  }, [selected, selectedMode, credentials, onComplete]);

  // Auto-run the connection test when entering the test step.
  const [pendingTest, setPendingTest] = useState(false);
  useEffect(() => {
    if (pendingTest && step === "test" && selected && !testing) {
      setPendingTest(false);
      handleTest();
    }
  }, [pendingTest, step, selected, testing, handleTest]);

  const allFields = [
    ...(selected?.common_fields ?? []),
    ...(selectedMode?.fields ?? []),
  ];
  const canTest = selectedMode && allFields.every(
    (f: ProviderField) => f.optional || credentials[f.key]?.trim(),
  );

  const handleBack = () => {
    if (step === "test" && selected && selectedMode && hasFields(selected, selectedMode)) {
      setStep("credentials");
    } else if (step === "test" || step === "credentials") {
      // Go back to auth_mode if there are multiple, otherwise provider.
      const available = selected?.auth_modes.filter((m) => m.available) ?? [];
      setStep(available.length > 1 ? "auth_mode" : "provider");
    } else if (step === "auth_mode") {
      setStep("provider");
    }
  };

  // Determine the active setup_help and setup_url from the selected mode.
  const setupHelp = selectedMode?.setup_help;
  const setupUrl = selectedMode?.setup_url;

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-ground p-6">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8 relative">
          {onCancel && (
            <button
              onClick={onCancel}
              aria-label="Close"
              className="absolute right-0 top-0 p-1 text-body-faint hover:text-body-muted transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <h1 className="text-3xl font-display text-body-heading mb-2">
            {onCancel ? "AI Provider Settings" : "Welcome to Clarity"}
          </h1>
          <p className="text-sm text-body-muted">
            {onCancel ? "Update your AI provider connection." : "Let's connect to an AI provider to get started."}
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {(["provider", "auth_mode", "credentials", "test"] as Step[]).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && <div className="w-8 h-px bg-border" />}
              <div
                className={`w-2 h-2 rounded-full transition-colors ${
                  s === step ? "bg-accent-focus" : "bg-border"
                }`}
              />
            </div>
          ))}
        </div>

        {/* Step: Provider selection */}
        {step === "provider" && (
          <div className="space-y-3 animate-fade-up">
            <h2 className="text-lg font-display text-body-heading mb-4">
              Which AI service would you like to use?
            </h2>
            {providers.map((p) => (
              <button
                key={p.name}
                onClick={() => handleSelectProvider(p)}
                className="w-full text-left p-4 rounded-xl border border-border
                  bg-surface hover:border-accent/40 hover:bg-surface-dim
                  transition-all duration-150 group"
              >
                <div className="font-medium text-body-heading group-hover:text-accent-focus transition-colors">
                  {p.display_name}
                </div>
                <div className="text-xs text-body-muted mt-0.5">
                  {p.description}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Step: Auth mode selection */}
        {step === "auth_mode" && selected && (
          <div className="space-y-3 animate-fade-up">
            <div className="flex items-center gap-3 mb-2">
              <button
                onClick={() => setStep("provider")}
                className="text-body-muted hover:text-body-heading transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
              </button>
              <h2 className="text-lg font-display text-body-heading">
                How would you like to sign in?
              </h2>
            </div>
            {selected.auth_modes.map((mode, i) => (
              <button
                key={mode.name}
                onClick={() => mode.available && handleSelectAuthMode(mode)}
                disabled={!mode.available}
                className={`w-full text-left p-4 rounded-xl border transition-all duration-150 group
                  ${mode.available
                    ? "border-border bg-surface hover:border-accent/40 hover:bg-surface-dim"
                    : "border-border/50 bg-surface/50 opacity-50 cursor-not-allowed"
                  }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${mode.available ? "text-body-heading group-hover:text-accent-focus" : "text-body-muted"} transition-colors`}>
                    {mode.display_name}
                  </span>
                  {i === 0 && mode.available && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-focus/15 text-accent-focus font-medium">
                      Recommended
                    </span>
                  )}
                  {!mode.available && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-dim text-body-faint font-medium">
                      Not installed
                    </span>
                  )}
                </div>
                <div className="text-xs text-body-muted mt-0.5">
                  {mode.description}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Step: Credentials */}
        {step === "credentials" && selected && selectedMode && (
          <div className="space-y-4 animate-fade-up">
            <div className="flex items-center gap-3 mb-2">
              <button
                onClick={handleBack}
                className="text-body-muted hover:text-body-heading transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
              </button>
              <h2 className="text-lg font-display text-body-heading">
                {selected.display_name} &mdash; {selectedMode.display_name}
              </h2>
            </div>

            {setupHelp && (
              <div className="p-3.5 rounded-lg bg-surface border border-border text-xs text-body-muted leading-relaxed">
                {setupHelp}
                {setupUrl && (
                  <>
                    {" "}
                    <a
                      href={setupUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent-focus hover:underline"
                    >
                      Open dashboard &rarr;
                    </a>
                  </>
                )}
              </div>
            )}

            {/* Common fields (e.g. Azure endpoint) */}
            {selected.common_fields && selected.common_fields.length > 0 && (
              <ProviderFieldList
                fields={selected.common_fields}
                credentials={credentials}
                onChange={setCredentials}
              />
            )}

            {/* Auth-mode-specific fields */}
            {selectedMode.fields.length > 0 && (
              <ProviderFieldList
                fields={selectedMode.fields}
                credentials={credentials}
                onChange={setCredentials}
              />
            )}

            <button
              onClick={() => { setPendingTest(true); setStep("test"); }}
              disabled={!canTest}
              className="w-full mt-2 px-4 py-2.5 rounded-lg bg-accent-focus text-white text-sm
                hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
                transition-all"
            >
              Test Connection
            </button>
          </div>
        )}

        {/* Step: Test & save */}
        {step === "test" && selected && selectedMode && (
          <div className="space-y-4 animate-fade-up">
            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleBack}
                className="text-body-muted hover:text-body-heading transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
              </button>
              <h2 className="text-lg font-display text-body-heading">
                Testing {selected.display_name}
              </h2>
            </div>

            {/* Show setup guidance on test step for zero-field auth modes */}
            {!hasFields(selected, selectedMode) && setupHelp && !testResult && (
              <div className="p-3.5 rounded-lg bg-surface border border-border text-xs text-body-muted leading-relaxed">
                {setupHelp}
                {setupUrl && (
                  <>
                    {" "}
                    <a
                      href={setupUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent-focus hover:underline"
                    >
                      Learn more &rarr;
                    </a>
                  </>
                )}
              </div>
            )}

            {testing && (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-surface border border-border">
                <svg className="w-5 h-5 animate-spin text-accent-focus" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                  <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <span className="text-sm text-body-muted">Testing connection...</span>
              </div>
            )}

            {testResult && !testing && (
              <div
                className={`p-4 rounded-xl border ${
                  testResult.ok
                    ? "bg-green-500/5 border-green-500/20 text-green-400"
                    : "bg-red-500/5 border-red-500/20 text-red-400"
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg mt-px">{testResult.ok ? "\u2713" : "\u2717"}</span>
                  <div>
                    <p className="text-sm">{testResult.message}</p>
                    {testResult.hint && (
                      <p className="text-xs mt-1 opacity-80">{testResult.hint}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-3 mt-4">
              {!testResult?.ok && !testing && (
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-border text-sm
                    text-body-label hover:bg-surface-dim transition-all"
                >
                  Retry
                </button>
              )}
              {testResult?.ok && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-accent-focus text-white text-sm
                    hover:brightness-110 disabled:opacity-50 transition-all"
                >
                  {saving ? "Saving..." : "Save & Continue"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
