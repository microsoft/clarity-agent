import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";

const FRAMES = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'];
const FRAME_INTERVAL_MS = 1000;

/**
 * Updates the browser/window title with an animated thinking indicator
 * while the LLM is generating a response. Lets users know the agent is
 * still working when they've switched to another tab or window.
 *
 * Renders nothing — pure side effect.
 */
export default function TabTitle() {
  const { streaming } = useChat();
  const originalTitle = useRef<string | null>(null);

  useEffect(() => {
    if (originalTitle.current === null) {
      originalTitle.current = document.title;
    }
    const base = originalTitle.current;

    if (!streaming) {
      document.title = base;
      return;
    }

    // Animate the spinner. The frame index lives in a local variable
    // (not React state) so that the interval has its own stable closure
    // and we don't trigger re-renders on every tick.
    let frameIndex = 0;
    document.title = `${FRAMES[frameIndex]} ${base}`;
    const interval = setInterval(() => {
      frameIndex = (frameIndex + 1) % FRAMES.length;
      document.title = `${FRAMES[frameIndex]} ${base}`;
    }, FRAME_INTERVAL_MS);

    return () => {
      clearInterval(interval);
      document.title = base;
    };
  }, [streaming]);

  return null;
}
