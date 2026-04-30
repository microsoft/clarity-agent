interface EmptyStateAction {
  label: string;
  onClick: () => void;
  primary?: boolean;
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  heading: string;
  description: string;
  actions?: EmptyStateAction[];
}

const DefaultIcon = () => (
  <svg className="w-10 h-10 text-accent/40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
  </svg>
);

export default function EmptyState({ icon, heading, description, actions }: EmptyStateProps) {
  return (
    <div className="text-center py-16 px-6 animate-fade-up">
      <div className="flex justify-center mb-4">
        {icon ?? <DefaultIcon />}
      </div>
      <h2 className="text-2xl text-body-heading mb-2 font-display">
        {heading}
      </h2>
      <p className="text-sm text-body-muted max-w-md mx-auto leading-relaxed mb-6">
        {description}
      </p>
      {actions && actions.length > 0 && (
        <div className="flex flex-wrap justify-center gap-3">
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              className={`px-4 py-2 rounded-lg text-sm transition-all duration-150 ${
                a.primary
                  ? "bg-accent-focus text-white hover:brightness-110"
                  : "border border-border text-body-label hover:bg-surface-dim hover:border-accent/30"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
