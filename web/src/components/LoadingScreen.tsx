import { useEffect, useState } from "react";

interface Tagline {
  text: string;
  attribution?: string;
}

// TODO: Replace these with good quotes that are at least vaguely and thematically
// related to the the concept of "vision" and/or "clarity." Nothing that reads like
// inspirational quotes, business jargon, AI hype, or anything that you might hear
// in a startup pitch deck. Bonus points for deep classical and poetic references.
const TAGLINES: Tagline[] = [
  { text: "Think it through before you build it." },
  { text: "Structured thinking, AI-guided." },
  { text: "Anticipate failures before they find you." },
  { text: "Designed decisions, not accidental ones." },
  { text: "The best architecture starts with the right questions." },
];

export default function LoadingScreen() {
  const [taglineIndex, setTaglineIndex] = useState(
    () => Math.floor(Math.random() * TAGLINES.length),
  );
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setTaglineIndex(() => Math.floor(Math.random() * TAGLINES.length));
        setFade(true);
      }, 400);
    }, 10_000);
    return () => clearInterval(interval);
  }, []);

  const tagline = TAGLINES[taglineIndex];

  return (
    <div className="h-screen bg-surface-ground flex flex-col items-center justify-center select-none p-6">
      <div className="w-full max-w-lg">
        {/* Header — mirrors the setup wizard's layout */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-display text-body-heading mb-2">
            Clarity
          </h1>
          <p className="text-sm text-body-muted">
            Structured thinking agent
          </p>
        </div>

        {/* Quote card — the hero element */}
        <div
          className="rounded-xl border border-border bg-surface p-8 transition-opacity duration-400"
          style={{ opacity: fade ? 1 : 0 }}
        >
          <p className="text-xl font-display text-body-heading italic leading-relaxed text-center">
            {"\u201c"}{tagline.text}{"\u201d"}
          </p>
          {tagline.attribution && (
            <p className="text-sm text-body-muted mt-4 text-center font-body">
              {"\u2014 "}{tagline.attribution}
            </p>
          )}
        </div>

        {/* Loading indicator */}
        <div className="flex items-center justify-center gap-2 mt-8">
          <div className="flex gap-1.5">
            <span className="w-1.5 h-1.5 bg-accent-focus rounded-full animate-bounce" />
            <span className="w-1.5 h-1.5 bg-accent-focus rounded-full animate-bounce" style={{ animationDelay: "0.15s" }} />
            <span className="w-1.5 h-1.5 bg-accent-focus rounded-full animate-bounce" style={{ animationDelay: "0.3s" }} />
          </div>
          <span className="text-xs text-body-faint ml-1">Getting things ready</span>
        </div>
      </div>
    </div>
  );
}
