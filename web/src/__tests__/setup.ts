import "@testing-library/jest-dom/vitest";

// Polyfill crypto.randomUUID for jsdom (used by chatReducer)
if (!globalThis.crypto?.randomUUID) {
  let counter = 0;
  Object.defineProperty(globalThis, "crypto", {
    value: {
      ...globalThis.crypto,
      randomUUID: () => `test-uuid-${++counter}`,
    },
  });
}
