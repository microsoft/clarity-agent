import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import GLOSSARY from "../data/glossary";

interface GlossaryTermProps {
  term: string;
  children?: React.ReactNode;
}

/**
 * Wraps a term with a dotted-underline and a hover tooltip.
 * The tooltip is rendered via a portal so it isn't clipped by
 * parent overflow or z-index stacking contexts (e.g. the sidebar).
 */
export default function GlossaryTerm({ term, children }: GlossaryTermProps) {
  const definition = GLOSSARY[term];
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const spanRef = useRef<HTMLSpanElement>(null);

  if (!definition) {
    return <>{children ?? term}</>;
  }

  const show = () => {
    if (spanRef.current) {
      const rect = spanRef.current.getBoundingClientRect();
      setPos({
        top: rect.top + rect.height / 2,
        left: rect.right + 8,
      });
    }
    setVisible(true);
  };

  const hide = () => setVisible(false);

  return (
    <>
      <span
        ref={spanRef}
        className="border-b border-dotted border-current/40 cursor-help"
        onMouseEnter={show}
        onMouseLeave={hide}
      >
        {children ?? term}
      </span>
      {visible && pos && createPortal(
        <div
          className="fixed px-3 py-2 rounded-lg text-xs leading-relaxed
            bg-surface text-body border border-border shadow-xl
            w-56 pointer-events-none z-[9999]"
          style={{ top: pos.top, left: pos.left, transform: "translateY(-50%)" }}
        >
          {definition}
        </div>,
        document.body,
      )}
    </>
  );
}
