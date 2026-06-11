import { useEffect, useState } from "react";
import {
  dismissExploration,
  getOnboardingScenarios,
  startExploration,
} from "../api/client";
import type { ExplorationScenario } from "../types";
import ScenarioSelector from "./ScenarioSelector";

interface FirstScreenProps {
  /** Called when the user picks "Start with my problem". */
  onStartOwnProblem: () => void;
  /** Called when user picks a scenario — pass process name + scenario id. */
  onStartExploration: (scenarioId: string) => void;
  /** Called when user picks "Open a project" (launcher mode). */
  onOpenProject?: () => void;
}

type View = "welcome" | "scenarios";

export default function FirstScreen({
  onStartOwnProblem,
  onStartExploration,
  onOpenProject,
}: FirstScreenProps) {
  const [view, setView] = useState<View>("welcome");
  const [scenarios, setScenarios] = useState<ExplorationScenario[]>([]);
  const [loading, setLoading] = useState(false);

  // Prefetch scenarios in the background so the transition is instant.
  useEffect(() => {
    getOnboardingScenarios()
      .then((r) => setScenarios(r.scenarios))
      .catch(() => {});
  }, []);

  const handleStartExploration = () => {
    setView("scenarios");
  };

  const handleScenarioSelected = async (scenarioId: string) => {
    setLoading(true);
    try {
      await startExploration(scenarioId);
      onStartExploration(scenarioId);
    } catch {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    await dismissExploration().catch(() => {});
    onStartOwnProblem();
  };

  if (view === "scenarios") {
    return (
      <ScenarioSelector
        scenarios={scenarios}
        onSelect={handleScenarioSelected}
        onUseOwnProblem={onStartOwnProblem}
        onBack={() => setView("welcome")}
        loading={loading}
      />
    );
  }

  return (
    <div className="text-center py-16 px-6 animate-fade-up">
      <div className="flex justify-center mb-6">
        <svg
          className="w-12 h-12 text-accent/50"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
          />
        </svg>
      </div>

      <h2 className="text-2xl text-body-heading mb-3 font-display">
        Think through something that matters.
      </h2>
      <p className="text-sm text-body-muted max-w-lg mx-auto leading-relaxed mb-10">
        Clarity helps you frame consequential problems, challenge assumptions,
        uncover failure modes, and preserve the reasoning as a project you can
        revisit.
      </p>

      <div className="flex flex-col sm:flex-row justify-center gap-3 max-w-xl mx-auto">
        <button
          onClick={onStartOwnProblem}
          className="px-5 py-2.5 rounded-lg text-sm bg-accent-focus text-white hover:brightness-110 transition-all duration-150"
        >
          Start with my problem
        </button>
        <button
          onClick={handleStartExploration}
          className="px-5 py-2.5 rounded-lg text-sm bg-accent-focus text-white hover:brightness-110 transition-all duration-150"
        >
          Try a five-minute exploration
        </button>
        {onOpenProject && (
          <button
            onClick={onOpenProject}
            className="px-5 py-2.5 rounded-lg text-sm border border-border text-body-label hover:bg-surface-dim hover:border-accent/30 transition-all duration-150"
          >
            Open a project
          </button>
        )}
      </div>

      <div className="mt-8">
        <button
          onClick={handleDismiss}
          className="text-xs text-body-muted hover:text-body-label transition-colors"
        >
          Skip — I know how Clarity works
        </button>
      </div>
    </div>
  );
}
