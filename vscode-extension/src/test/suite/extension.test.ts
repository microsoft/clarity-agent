import * as assert from "assert";
import * as vscode from "vscode";

suite("Extension Activation", () => {
  test("extension should be present", () => {
    const ext = vscode.extensions.getExtension("clarity-agent.clarity-agent");
    assert.ok(ext, "Extension not found. Check publisher and name in package.json.");
  });

  test("extension should activate", async () => {
    const ext = vscode.extensions.getExtension("clarity-agent.clarity-agent");
    if (!ext) {
      assert.fail("Extension not found");
      return;
    }
    await ext.activate();
    assert.strictEqual(ext.isActive, true);
  });

  test("all commands should be registered", async () => {
    const commands = await vscode.commands.getCommands(true);
    const expected = [
      "clarity.open",
      "clarity.openProject",
      "clarity.doctor",
      "clarity.restart",
      "clarity.switchProject",
      "clarity.setup",
      "clarity.selectModel",
      "clarity.generatePacket",
      "clarity.listProcesses",
      "clarity.viewTranscripts",
      "clarity.sendFeedback",
      "clarity.configureMcp",
      "clarity.refreshProtocol",
      "clarity.openProtocolDocument",
    ];

    for (const cmd of expected) {
      assert.ok(
        commands.includes(cmd),
        `Command '${cmd}' not registered`,
      );
    }
  });
});

suite("Backend Manager", () => {
  test("backend starts in stopped state", () => {
    // This test verifies the BackendManager module can be imported
    // and constructed without errors. Actual backend start requires
    // a Python environment and is tested via integration tests.
    const { BackendManager } = require("../../backendManager");
    const mgr = new BackendManager("/tmp/fake-dir", {
      onStateChange: () => {},
      onLog: () => {},
    });
    assert.strictEqual(mgr.state, "stopped");
    assert.strictEqual(mgr.port, 0);
    mgr.dispose();
  });
});