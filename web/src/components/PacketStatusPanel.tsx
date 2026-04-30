import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPacketStatus } from "../api/client";
import type { PacketStatusData, ProcessPhase } from "../types";

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  current: { bg: "bg-status-ok-bg", text: "text-status-ok-text", label: "Current" },
  stale: { bg: "bg-status-warn-bg", text: "text-status-warn-text", label: "Stale" },
  empty: { bg: "bg-surface-muted", text: "text-body-label", label: "Empty" },
  missing: { bg: "bg-status-error-bg", text: "text-status-error-text", label: "Missing" },
  untracked: { bg: "bg-status-info-bg", text: "text-status-info-text", label: "Untracked" },
};

const PHASE_BADGE: Record<ProcessPhase["status"], { bg: string; text: string; label: string }> = {
  recommended: { bg: "bg-status-warn-bg", text: "text-status-warn-text", label: "Recommended" },
  available: { bg: "bg-surface-muted", text: "text-body-label", label: "Available" },
  unavailable: { bg: "bg-surface-dim", text: "text-body-faint", label: "Unavailable" },
};

export default function PacketStatusPanel() {
  const navigate = useNavigate();
  const [data, setData] = useState<PacketStatusData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPacketStatus()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="p-8 animate-fade-up">
        <p className="text-status-error text-sm">
          {error.includes("404")
            ? "No .clarity-protocol/ directory found."
            : `Error: ${error}`}
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-body-faint animate-pulse-warm">
        Loading status...
      </div>
    );
  }

  const { report, next_action, process_availability } = data;
  const recommended = process_availability.filter((p) => p.status === "recommended");
  const available = process_availability.filter((p) => p.status === "available");
  const unavailable = process_availability.filter((p) => p.status === "unavailable");

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div className="animate-fade-up">
        <h1
          className="text-2xl text-body-heading font-display"
        >
          Packet Status
        </h1>
        <p className="text-sm text-body-muted mt-1">
          Document dependencies and staleness tracking
        </p>
      </div>

      {/* Next action card */}
      {next_action && (
        <div className="bg-accent-surface border border-accent-surface-border rounded-xl p-5 animate-fade-up delay-75 shadow-sm">
          <h2 className="text-xs font-medium tracking-widest uppercase text-accent-surface-text mb-2">
            Recommended Next Step
          </h2>
          <p className="text-sm text-accent-surface-body leading-relaxed">
            <strong>{next_action.action}</strong>: {next_action.document}
            {next_action.process && (
              <span className="text-accent-surface-muted"> — run {next_action.process}</span>
            )}
          </p>
          <p className="text-xs text-accent-surface-muted mt-2">{next_action.reason}</p>
        </div>
      )}

      {/* Summary counts */}
      <div className="flex flex-wrap gap-2 animate-fade-up delay-150">
        {Object.entries(report.summary).map(([status, docs]) => {
          const badge = STATUS_BADGE[status];
          if (!badge || docs.length === 0) return null;
          return (
            <span
              key={status}
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full ${badge.bg} ${badge.text}`}
            >
              {badge.label}: {docs.length}
            </span>
          );
        })}
      </div>

      {/* Process availability */}
      {process_availability.length > 0 && (
        <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm animate-fade-up delay-200">
          <div className="px-5 py-3.5 border-b border-border">
            <h2 className="text-xs font-medium tracking-widest uppercase text-body-label">
              Process Availability
            </h2>
          </div>
          <div className="divide-y divide-border-dim">
            {[
              { label: "Recommended", items: recommended },
              { label: "Available", items: available },
              { label: "Unavailable", items: unavailable },
            ]
              .filter((group) => group.items.length > 0)
              .map((group) => (
                <div key={group.label} className="px-5 py-3">
                  <p className="text-[10px] font-medium tracking-widest uppercase text-body-faint mb-2">
                    {group.label}
                  </p>
                  <div className="space-y-1.5">
                    {group.items.map((p) => {
                      const badge = PHASE_BADGE[p.status];
                      return (
                        <div key={p.process} className="flex items-baseline gap-2.5">
                          <span
                            className={`shrink-0 text-xs font-medium px-2.5 py-0.5 rounded-full font-mono ${badge.bg} ${badge.text}`}
                            style={{ fontSize: "0.7rem" }}
                          >
                            {p.process}
                          </span>
                          <span className="text-xs text-body-muted">{p.reason}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Document table */}
      <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm animate-fade-up delay-300">
        <table className="w-full text-sm">
          <thead className="border-b border-border">
            <tr className="bg-surface-dim">
              <th className="text-left px-5 py-3 text-[10px] font-medium tracking-widest uppercase text-body-faint">
                Document
              </th>
              <th className="text-left px-5 py-3 text-[10px] font-medium tracking-widest uppercase text-body-faint">
                Status
              </th>
              <th className="text-left px-5 py-3 text-[10px] font-medium tracking-widest uppercase text-body-faint">
                Dependencies
              </th>
              <th className="text-left px-5 py-3 text-[10px] font-medium tracking-widest uppercase text-body-faint">
                Reason
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-dim">
            {Object.entries(report.documents).map(([doc, info]) => {
              const badge = STATUS_BADGE[info.status] ?? STATUS_BADGE.missing;
              return (
                <tr key={doc} className="hover:bg-surface-dim/50 transition-colors">
                  <td className="px-5 py-2.5">
                    <button
                      onClick={() => navigate("/protocol", { state: { selectedFile: doc } })}
                      className="text-accent hover:text-accent-hover text-xs transition-colors font-mono"
                    >
                      {doc}
                    </button>
                  </td>
                  <td className="px-5 py-2.5">
                    <span
                      className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${badge.bg} ${badge.text}`}
                    >
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 text-xs text-body-muted">
                    {info.dependencies.length > 0
                      ? info.dependencies.join(", ")
                      : "\u2014"}
                  </td>
                  <td className="px-5 py-2.5 text-xs text-body-muted">
                    {info.stale_because.length > 0
                      ? info.stale_because.map((s) => s.doc).join(", ") + " changed"
                      : "\u2014"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
