// @ts-check
/**
 * Bundle the clarity-agent Python source and runtime files into the
 * extension directory so the VSIX is self-contained.
 *
 * Usage: node bundle.js
 *
 * Creates vscode-extension/bundled/ with everything needed to run
 * `python clarity.py web <project>` without a separate clone.
 */

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
const BUNDLED = path.join(__dirname, "bundled");

/** Directories/files to copy from the repo root into bundled/. */
const ITEMS = [
  // Entry point
  "clarity.py",
  "pyproject.toml",
  "AGENTS.md",

  // Python package
  "src",

  // Process guides and thinkers (runtime data read by the agent)
  "processes",
  "thinkers",
  "catalogs",

  // Built React frontend
  "web/dist",
];

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const child of fs.readdirSync(src)) {
      // Skip __pycache__, .pyc, node_modules, .git
      if (
        child === "__pycache__" ||
        child === "node_modules" ||
        child === ".git" ||
        child.endsWith(".pyc")
      ) {
        continue;
      }
      copyRecursive(path.join(src, child), path.join(dest, child));
    }
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

function clean() {
  if (fs.existsSync(BUNDLED)) {
    fs.rmSync(BUNDLED, { recursive: true, force: true });
  }
}

function bundle() {
  console.log("Bundling clarity-agent into vscode-extension/bundled/...");
  clean();
  fs.mkdirSync(BUNDLED, { recursive: true });

  for (const item of ITEMS) {
    const src = path.join(REPO_ROOT, item);
    // Preserve relative path structure: "web/dist" -> "bundled/web/dist"
    const dest = path.join(BUNDLED, item);

    if (!fs.existsSync(src)) {
      console.warn(`  SKIP (not found): ${item}`);
      continue;
    }

    console.log(`  COPY: ${item}`);
    copyRecursive(src, dest);
  }

  // Count files
  let count = 0;
  function countFiles(dir) {
    for (const child of fs.readdirSync(dir)) {
      const full = path.join(dir, child);
      if (fs.statSync(full).isDirectory()) countFiles(full);
      else count++;
    }
  }
  countFiles(BUNDLED);
  console.log(`\nBundled ${count} files into bundled/`);
}

bundle();