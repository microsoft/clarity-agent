import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { generatePacket, getPacketOptions } from "../api/client";
import type { PacketPart, PacketSource, PacketView } from "../types";

// Calibrated against real output: 75 real pages from ~25k words.
const WORDS_PER_PAGE = 330;

function getPartCheckState(
  sourceIds: string[],
  selected: Set<string>,
): "all" | "none" | "some" {
  const count = sourceIds.filter((id) => selected.has(id)).length;
  if (count === 0) return "none";
  if (count === sourceIds.length) return "all";
  return "some";
}

function estimatePages(
  sourceIds: string[],
  sizes: Record<string, number>,
): number {
  const words = sourceIds.reduce((sum, id) => sum + (sizes[id] ?? 0), 0);
  if (words <= 0) return 0;
  return Math.max(1, Math.round(words / WORDS_PER_PAGE));
}

// ---------------------------------------------------------------------------
// Sortable source item
// ---------------------------------------------------------------------------

function formatSourcePages(wordCount: number): string {
  if (wordCount <= 0) return "";
  const pages = wordCount / WORDS_PER_PAGE;
  if (pages < 0.5) return "<1pp";
  return `~${Math.round(pages)}pp`;
}

function SortableSourceItem({
  source,
  checked,
  wordCount,
  onToggle,
}: {
  source: PacketSource;
  checked: boolean;
  wordCount: number;
  onToggle: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: source.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const pageLabel = formatSourcePages(wordCount);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-default
        transition-all duration-200 ${
          checked
            ? "border-accent/30 bg-accent-surface"
            : "border-border hover:border-border-strong hover:bg-surface-dim"
        }`}
    >
      <button
        type="button"
        className="touch-none text-body-faint hover:text-body-muted cursor-grab active:cursor-grabbing
          p-0.5 -ml-1 flex-shrink-0"
        aria-label="Drag to reorder"
        {...attributes}
        {...listeners}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <circle cx="4" cy="2" r="1" />
          <circle cx="8" cy="2" r="1" />
          <circle cx="4" cy="6" r="1" />
          <circle cx="8" cy="6" r="1" />
          <circle cx="4" cy="10" r="1" />
          <circle cx="8" cy="10" r="1" />
        </svg>
      </button>
      <label className="flex items-center gap-3 cursor-pointer flex-1 min-w-0">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="rounded border-border-strong text-accent focus:ring-accent/30
            w-4 h-4 transition-colors flex-shrink-0"
        />
        <span className="text-sm text-body-label truncate">{source.title}</span>
      </label>
      {pageLabel && (
        <span className="text-xs text-body-faint whitespace-nowrap flex-shrink-0">
          {pageLabel}
        </span>
      )}
    </div>
  );
}

/** Static (non-sortable) copy of a source item, rendered inside DragOverlay. */
function SourceItemOverlay({ source, checked }: { source: PacketSource; checked: boolean }) {
  return (
    <div
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-grabbing
        shadow-lg ${
          checked
            ? "border-accent/30 bg-accent-surface"
            : "border-border bg-surface"
        }`}
    >
      <span className="text-body-faint p-0.5 -ml-1 flex-shrink-0">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <circle cx="4" cy="2" r="1" />
          <circle cx="8" cy="2" r="1" />
          <circle cx="4" cy="6" r="1" />
          <circle cx="8" cy="6" r="1" />
          <circle cx="4" cy="10" r="1" />
          <circle cx="8" cy="10" r="1" />
        </svg>
      </span>
      <span className="text-sm text-body-label">{source.title}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirmation dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-2xl shadow-xl p-6 max-w-sm mx-4 animate-fade-up">
        <p className="text-sm text-body-label leading-relaxed">{message}</p>
        <div className="flex justify-end gap-3 mt-5">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-body-label rounded-lg border border-border
              hover:bg-surface-dim transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm text-white font-medium bg-accent rounded-lg
              hover:bg-accent-hover transition-colors"
          >
            Discard changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PacketDialog() {
  const [sources, setSources] = useState<PacketSource[]>([]);
  const [formats, setFormats] = useState<string[]>([]);
  const [views, setViews] = useState<PacketView[]>([]);
  const [sourceSizes, setSourceSizes] = useState<Record<string, number>>({});

  // Working state — parts and selection can diverge from the named view.
  const [parts, setParts] = useState<PacketPart[]>([]);
  const [selectedView, setSelectedView] = useState<string>("complete");
  const [isCustom, setIsCustom] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());

  // Pending view switch awaiting confirmation when custom is dirty.
  const [pendingViewSwitch, setPendingViewSwitch] = useState<string | null>(null);

  const [format, setFormat] = useState("docx");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // ------------------------------------------------------------------
  // Load options from backend
  // ------------------------------------------------------------------

  useEffect(() => {
    getPacketOptions()
      .then((data) => {
        setSources(data.sources);
        setFormats(data.formats);
        setViews(data.views ?? []);
        setSourceSizes(data.source_sizes ?? {});

        // Default to "complete" view.
        const completeView = (data.views ?? []).find((v) => v.id === "complete");
        if (completeView) {
          setParts(completeView.parts);
          setSelectedSources(new Set(completeView.parts.flatMap((p) => p.source_ids)));
        } else {
          setParts(data.parts ?? []);
          setSelectedSources(new Set(data.sources.map((s) => s.id)));
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  // ------------------------------------------------------------------
  // View selection
  // ------------------------------------------------------------------

  /** Apply a named view (no confirmation, unconditional). */
  const applyView = useCallback(
    (viewId: string) => {
      if (viewId === "custom") {
        setSelectedView("custom");
        setIsCustom(true);
        setIsDirty(false);
        return;
      }
      const view = views.find((v) => v.id === viewId);
      if (view) {
        setSelectedView(viewId);
        setIsCustom(false);
        setIsDirty(false);
        setParts(view.parts);
        setSelectedSources(new Set(view.parts.flatMap((p) => p.source_ids)));
      }
    },
    [views],
  );

  /** Request a view change — may trigger confirmation if custom is dirty. */
  const handleViewChange = useCallback(
    (viewId: string) => {
      if (isCustom && isDirty && viewId !== "custom") {
        setPendingViewSwitch(viewId);
        return;
      }
      applyView(viewId);
    },
    [isCustom, isDirty, applyView],
  );

  const confirmViewSwitch = useCallback(() => {
    if (pendingViewSwitch) {
      applyView(pendingViewSwitch);
      setPendingViewSwitch(null);
    }
  }, [pendingViewSwitch, applyView]);

  const cancelViewSwitch = useCallback(() => {
    setPendingViewSwitch(null);
  }, []);

  // Switch to custom whenever user modifies sections.
  const goCustom = useCallback(() => {
    if (!isCustom) {
      setSelectedView("custom");
      setIsCustom(true);
    }
    setIsDirty(true);
  }, [isCustom]);

  // ------------------------------------------------------------------
  // Editable part titles (custom mode only)
  // ------------------------------------------------------------------

  const renamePart = useCallback(
    (partIndex: number, newTitle: string) => {
      goCustom();
      setParts((prev) =>
        prev.map((p, i) => (i === partIndex ? { ...p, title: newTitle } : p)),
      );
    },
    [goCustom],
  );

  // ------------------------------------------------------------------
  // Checkbox toggles
  // ------------------------------------------------------------------

  const toggleSource = useCallback(
    (sourceId: string) => {
      goCustom();
      setSelectedSources((prev) => {
        const next = new Set(prev);
        if (next.has(sourceId)) next.delete(sourceId);
        else next.add(sourceId);
        return next;
      });
    },
    [goCustom],
  );

  const togglePart = useCallback(
    (sourceIds: string[]) => {
      goCustom();
      setSelectedSources((prev) => {
        const next = new Set(prev);
        const allSelected = sourceIds.every((id) => next.has(id));
        if (allSelected) sourceIds.forEach((id) => next.delete(id));
        else sourceIds.forEach((id) => next.add(id));
        return next;
      });
    },
    [goCustom],
  );

  // ------------------------------------------------------------------
  // Drag-and-drop reordering (cross-container support)
  // ------------------------------------------------------------------

  const [activeId, setActiveId] = useState<string | null>(null);
  const dragOriginalParts = useRef<PacketPart[] | null>(null);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      setActiveId(event.active.id as string);
      dragOriginalParts.current = parts;
    },
    [parts],
  );

  /** Move items between containers in real-time so the UI stays in sync. */
  const handleDragOver = useCallback((event: DragOverEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const aid = active.id as string;
    const oid = over.id as string;

    setParts((prev) => {
      const srcIdx = prev.findIndex((p) => p.source_ids.includes(aid));
      const dstIdx = prev.findIndex((p) => p.source_ids.includes(oid));
      if (srcIdx === -1 || dstIdx === -1 || srcIdx === dstIdx) return prev;

      return prev.map((part, i) => {
        if (i === srcIdx) {
          return { ...part, source_ids: part.source_ids.filter((id) => id !== aid) };
        }
        if (i === dstIdx) {
          const ids = [...part.source_ids];
          const insertAt = ids.indexOf(oid);
          ids.splice(insertAt, 0, aid);
          return { ...part, source_ids: ids };
        }
        return part;
      });
    });
  }, []);

  /** Finalize position within the (possibly new) container. */
  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      setActiveId(null);
      dragOriginalParts.current = null;

      if (!over || active.id === over.id) return;

      goCustom();
      setParts((prev) => {
        const aid = active.id as string;
        const oid = over.id as string;
        const idx = prev.findIndex((p) => p.source_ids.includes(aid));
        const dstIdx = prev.findIndex((p) => p.source_ids.includes(oid));
        if (idx === -1 || dstIdx === -1 || idx !== dstIdx) return prev;

        return prev.map((part, i) => {
          if (i !== idx) return part;
          const ids = [...part.source_ids];
          const from = ids.indexOf(aid);
          const to = ids.indexOf(oid);
          ids.splice(from, 1);
          ids.splice(to, 0, aid);
          return { ...part, source_ids: ids };
        });
      });
    },
    [goCustom],
  );

  /** Restore original parts if the drag is cancelled (e.g. Escape). */
  const handleDragCancel = useCallback(() => {
    setActiveId(null);
    if (dragOriginalParts.current) {
      setParts(dragOriginalParts.current);
      dragOriginalParts.current = null;
    }
  }, []);

  // ------------------------------------------------------------------
  // Page estimates for each view
  // ------------------------------------------------------------------

  const viewPageEstimates = useMemo(() => {
    const estimates: Record<string, number> = {};
    for (const v of views) {
      estimates[v.id] = estimatePages(
        v.parts.flatMap((p) => p.source_ids),
        sourceSizes,
      );
    }
    return estimates;
  }, [views, sourceSizes]);

  // Live page total for the custom view — only checked sources.
  const customPages = useMemo(() => {
    const checkedIds = parts
      .flatMap((p) => p.source_ids)
      .filter((id) => selectedSources.has(id));
    return estimatePages(checkedIds, sourceSizes);
  }, [parts, selectedSources, sourceSizes]);

  // ------------------------------------------------------------------
  // Edit-title-in-place: focus a part title input after switching to custom
  // ------------------------------------------------------------------

  const focusPartRef = useRef<number | null>(null);

  const handleEditPartTitle = useCallback(
    (partIndex: number) => {
      if (!isCustom) {
        setSelectedView("custom");
        setIsCustom(true);
      }
      focusPartRef.current = partIndex;
    },
    [isCustom],
  );

  // ------------------------------------------------------------------
  // Generate
  // ------------------------------------------------------------------

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setSavedPath(null);
    try {
      let sections: string[] | null;
      let viewArg: string | null;

      if (isCustom) {
        // Send the ordered list of checked sources.
        const orderedIds = parts.flatMap((p) => p.source_ids);
        sections = orderedIds.filter((id) => selectedSources.has(id));
        viewArg = null;
      } else {
        sections =
          selectedSources.size === sources.length ? null : Array.from(selectedSources);
        viewArg = selectedView;
      }

      const blob = await generatePacket(sections, format, viewArg);
      const ext = format === "markdown" ? "md" : format;
      const defaultName = `packet.${ext}`;

      const inTauri = "__TAURI_INTERNALS__" in window || "__TAURI__" in window;

      if (inTauri) {
        // Native save dialog → write file → show confirmation.
        const { save } = await import("@tauri-apps/plugin-dialog");
        const { writeFile } = await import("@tauri-apps/plugin-fs");

        const path = await save({
          defaultPath: defaultName,
          title: "Save packet",
        });
        if (!path) {
          // User cancelled.
          setGenerating(false);
          return;
        }

        const bytes = new Uint8Array(await blob.arrayBuffer());
        await writeFile(path, bytes);
        setSavedPath(path);
      } else {
        // Browser fallback: anchor-click download.
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = defaultName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setSavedPath(defaultName);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }, [isCustom, parts, selectedSources, sources.length, format, selectedView]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      {/* Confirmation dialog */}
      {pendingViewSwitch && (
        <ConfirmDialog
          message="You have unsaved changes to your custom view. Switching to a preset will discard them."
          onConfirm={confirmViewSwitch}
          onCancel={cancelViewSwitch}
        />
      )}

      {/* Header */}
      <div className="animate-fade-up">
        <h1 className="text-2xl text-body-heading font-display">Review Packet</h1>
        <p className="text-sm text-body-muted mt-1 leading-relaxed">
          Choose a view, adjust sections if needed, then generate.
        </p>
      </div>

      {/* Two-column: views + sections */}
      <div className="flex gap-6 animate-fade-up delay-75">
        {/* Left column: Views */}
        {views.length > 0 && (
          <div className="w-48 flex-shrink-0 space-y-2">
            <h2 className="text-xs font-medium tracking-widest uppercase text-body-faint mb-3">
              View
            </h2>
            {views.map((v) => {
              const isActive = !isCustom && selectedView === v.id;
              const pages = viewPageEstimates[v.id] ?? 0;
              return (
                <button
                  key={v.id}
                  onClick={() => handleViewChange(v.id)}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-all duration-200 ${
                    isActive
                      ? "border-accent/30 bg-accent-surface shadow-sm"
                      : "border-border hover:border-border-strong hover:bg-surface-dim"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className={`text-sm font-medium ${
                        isActive ? "text-accent-surface-body" : "text-body-heading"
                      }`}
                    >
                      {v.title}
                    </span>
                    {pages > 0 && (
                      <span className="text-xs text-body-faint whitespace-nowrap">
                        ~{pages}pp
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-body-muted mt-1 leading-snug line-clamp-2">
                    {v.description}
                  </p>
                </button>
              );
            })}

            {/* Custom option */}
            <button
              onClick={() => handleViewChange("custom")}
              className={`w-full text-left px-4 py-3 rounded-xl border transition-all duration-200 ${
                isCustom
                  ? "border-accent/30 bg-accent-surface shadow-sm"
                  : "border-border hover:border-border-strong hover:bg-surface-dim"
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={`text-sm font-medium ${
                    isCustom ? "text-accent-surface-body" : "text-body-heading"
                  }`}
                >
                  Custom
                </span>
                {isCustom && customPages > 0 && (
                  <span className="text-xs text-body-faint whitespace-nowrap">
                    ~{customPages}pp
                  </span>
                )}
              </div>
              <p className="text-xs text-body-muted mt-1 leading-snug">
                Manually selected and ordered.
              </p>
            </button>
          </div>
        )}

        {/* Right column: Sections */}
        <div className="flex-1 min-w-0 space-y-4">
          <h2 className="text-xs font-medium tracking-widest uppercase text-body-faint mb-3">
            Sections
          </h2>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
          >
            {parts.map((part, partIndex) => {
              const checkState = getPartCheckState(part.source_ids, selectedSources);
              const partSources = part.source_ids
                .map((id) => sources.find((s) => s.id === id))
                .filter(Boolean) as PacketSource[];
              const partPages = estimatePages(
                part.source_ids.filter((id) => selectedSources.has(id)),
                sourceSizes,
              );

              return (
                <div key={partIndex} className="rounded-xl border border-border p-4">
                  {/* Part header with toggle-all checkbox */}
                  <div className="flex items-center gap-3 mb-3">
                    <input
                      type="checkbox"
                      checked={checkState === "all"}
                      ref={(el) => {
                        if (el) el.indeterminate = checkState === "some";
                      }}
                      onChange={() => togglePart(part.source_ids)}
                      className="rounded border-border-strong text-accent focus:ring-accent/30
                        w-4 h-4 transition-colors cursor-pointer"
                    />
                    {isCustom ? (
                      <input
                        type="text"
                        value={part.title}
                        onChange={(e) => renamePart(partIndex, e.target.value)}
                        ref={(el) => {
                          if (el && focusPartRef.current === partIndex) {
                            el.focus();
                            el.select();
                            focusPartRef.current = null;
                          }
                        }}
                        className="text-sm font-medium text-body-heading bg-transparent
                          border-b border-dashed border-border-strong
                          focus:border-accent focus:outline-none
                          px-0 py-0 flex-1 min-w-0"
                      />
                    ) : (
                      <span className="text-sm font-medium text-body-heading flex items-center gap-2">
                        {part.title}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditPartTitle(partIndex);
                          }}
                          className="text-body-faint hover:text-body-muted transition-colors"
                          aria-label="Edit section title"
                          title="Edit in custom view"
                        >
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M8.5 1.5l2 2L4 10H2v-2z" />
                          </svg>
                        </button>
                      </span>
                    )}
                    {partPages > 0 && (
                      <span className="text-xs text-body-faint whitespace-nowrap ml-auto">
                        {partPages}pp
                      </span>
                    )}
                  </div>

                  {/* Sortable source list */}
                  <SortableContext
                    items={part.source_ids}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="space-y-1.5 ml-7">
                      {partSources.map((source) => (
                        <SortableSourceItem
                          key={source.id}
                          source={source}
                          checked={selectedSources.has(source.id)}
                          wordCount={sourceSizes[source.id] ?? 0}
                          onToggle={() => toggleSource(source.id)}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </div>
              );
            })}
            <DragOverlay dropAnimation={null}>
              {activeId
                ? (() => {
                    const src = sources.find((s) => s.id === activeId);
                    return src ? (
                      <SourceItemOverlay
                        source={src}
                        checked={selectedSources.has(activeId)}
                      />
                    ) : null;
                  })()
                : null}
            </DragOverlay>
          </DndContext>
        </div>
      </div>

      {/* Format + Generate row */}
      <div className="flex items-center justify-between gap-6 animate-fade-up delay-150">
        <div className="flex gap-3">
          {formats.map((f) => (
            <label
              key={f}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border cursor-pointer
                transition-all duration-200 ${
                  format === f
                    ? "border-accent/30 bg-accent-surface shadow-sm"
                    : "border-border hover:border-border-strong hover:bg-surface-dim"
                }`}
            >
              <input
                type="radio"
                name="format"
                value={f}
                checked={format === f}
                onChange={() => setFormat(f)}
                className="border-border-strong text-accent focus:ring-accent/30 transition-colors"
              />
              <span className="text-sm text-body-label capitalize">{f}</span>
            </label>
          ))}
        </div>

        <div className="flex items-center gap-4">
          {error && <p className="text-sm text-status-error">{error}</p>}
          {savedPath && !error && (
            <p className="text-sm text-status-ok flex items-center gap-1.5">
              <span>{"\u2713"}</span>
              <span>Saved to {savedPath.split("/").pop()}</span>
            </p>
          )}
          <button
            onClick={handleGenerate}
            disabled={generating || selectedSources.size === 0}
            className="px-7 py-2.5 bg-accent text-white text-sm font-medium rounded-xl
              shadow-md shadow-shadow-accent/10
              hover:bg-accent-hover hover:shadow-lg
              active:scale-[0.98]
              disabled:bg-disabled disabled:shadow-none disabled:cursor-not-allowed
              transition-all duration-200"
          >
            {generating ? "Generating..." : "Generate & Download"}
          </button>
        </div>
      </div>
    </div>
  );
}
