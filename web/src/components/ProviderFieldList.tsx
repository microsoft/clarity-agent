import type { ProviderField } from "../types";

/** Renders a list of ProviderField inputs. Shared by SetupWizard and PreferencesPanel. */
export default function ProviderFieldList({
  fields,
  credentials,
  onChange,
}: {
  fields: ProviderField[];
  credentials: Record<string, string>;
  onChange: (creds: Record<string, string>) => void;
}) {
  return (
    <>
      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-xs text-body-label mb-1">
            {f.label}
            {f.optional && <span className="text-body-faint ml-1">(optional)</span>}
          </label>
          <input
            type={f.secret ? "password" : "text"}
            placeholder={f.placeholder}
            value={credentials[f.key] ?? ""}
            onChange={(e) => onChange({ ...credentials, [f.key]: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface-ground
              text-sm text-body-heading placeholder:text-body-faint
              focus:outline-none focus:border-accent-focus focus:ring-1 focus:ring-accent-focus/30
              transition-all"
          />
          {f.help && <p className="text-[11px] text-body-faint mt-1">{f.help}</p>}
        </div>
      ))}
    </>
  );
}
