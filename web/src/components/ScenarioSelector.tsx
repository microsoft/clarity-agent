import type { ExplorationScenario } from "../types";

interface ScenarioSelectorProps {
  scenarios: ExplorationScenario[];
  onSelect: (scenarioId: string) => void;
  onUseOwnProblem: () => void;
  onBack: () => void;
  loading?: boolean;
}

export default function ScenarioSelector({
  scenarios,
  onSelect,
  onUseOwnProblem,
  onBack,
  loading,
}: ScenarioSelectorProps) {
  return (
    <div className="py-12 px-6 animate-fade-up max-w-2xl mx-auto">
      <button
        onClick={onBack}
        className="text-xs text-body-muted hover:text-body-label mb-6 transition-colors"
      >
        &larr; Back
      </button>

      <h2 className="text-xl text-body-heading mb-2 font-display text-center">
        Choose a situation to think through
      </h2>
      <p className="text-sm text-body-muted text-center mb-8">
        Pick whichever one interests you. There is no correct choice.
      </p>

      <div className="space-y-3">
        {scenarios.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            disabled={loading}
            className="w-full text-left p-4 rounded-lg border border-border hover:border-accent/40 hover:bg-surface-dim transition-all duration-150 disabled:opacity-50 disabled:cursor-wait"
          >
            <h3 className="text-sm font-medium text-body-heading mb-1">
              {s.title}
            </h3>
            <p className="text-xs text-body-muted leading-relaxed">
              {s.description}
            </p>
          </button>
        ))}
      </div>

      <div className="text-center mt-6">
        <button
          onClick={onUseOwnProblem}
          disabled={loading}
          className="text-sm text-accent hover:text-accent-hover transition-colors disabled:opacity-50"
        >
          Use my own problem instead
        </button>
      </div>
    </div>
  );
}
