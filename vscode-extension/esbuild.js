// @ts-check
const esbuild = require("esbuild");

const production = process.argv.includes("--production");
const watch = process.argv.includes("--watch");

async function main() {
  // Main extension bundle
  const ctx = await esbuild.context({
    entryPoints: ["src/extension.ts"],
    bundle: true,
    format: "cjs",
    minify: production,
    sourcemap: !production,
    sourcesContent: false,
    platform: "node",
    outfile: "out/extension.js",
    external: ["vscode"],
    logLevel: "info",
  });

  // Test files (unbundled, separate outputs)
  const testCtx = await esbuild.context({
    entryPoints: [
      "src/test/runTest.ts",
      "src/test/suite/index.ts",
      "src/test/suite/extension.test.ts",
    ],
    bundle: false,
    format: "cjs",
    sourcemap: true,
    platform: "node",
    outdir: "out",
    outbase: "src",
    external: ["vscode", "mocha", "@vscode/test-electron", "glob"],
    logLevel: "info",
  });

  if (watch) {
    await ctx.watch();
    await testCtx.watch();
    console.log("Watching for changes...");
  } else {
    await ctx.rebuild();
    await testCtx.rebuild();
    await ctx.dispose();
    await testCtx.dispose();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});