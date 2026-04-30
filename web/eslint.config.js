import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";

export default tseslint.config(
  // Base JS recommended rules.
  js.configs.recommended,

  // TypeScript recommended rules.
  ...tseslint.configs.recommended,

  // React Hooks rules.
  {
    plugins: { "react-hooks": reactHooks },
    rules: {
      // Core hooks rules — must be errors.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // The v5 strict rules flag legitimate patterns (async data
      // fetching in effects, ref-syncing, self-referencing callbacks).
      // Keep them as warnings so they're visible but don't block CI.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
    },
  },

  // Accessibility rules.
  {
    plugins: { "jsx-a11y": jsxA11y },
    rules: jsxA11y.flatConfigs.recommended.rules,
  },

  // Project-specific overrides.
  {
    rules: {
      // TypeScript strict mode already catches unused vars via
      // noUnusedLocals / noUnusedParameters in tsconfig.json.
      "@typescript-eslint/no-unused-vars": "off",

      // Allow explicit `any` — the codebase uses it intentionally
      // in a few places (event handlers, generic tool schemas).
      "@typescript-eslint/no-explicit-any": "off",
    },
  },

  // Ignore build output.
  { ignores: ["dist/"] },
);
