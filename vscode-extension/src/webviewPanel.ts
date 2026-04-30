/**
 * Webview panel that displays the Clarity Agent React SPA.
 *
 * Uses an iframe pointing at the locally-running FastAPI backend,
 * which serves the same React app used by `clarity web`.
 */

import * as vscode from "vscode";

export class ClarityWebviewPanel {
  public static readonly viewType = "clarity.panel";

  private static instance: ClarityWebviewPanel | undefined;
  private readonly panel: vscode.WebviewPanel;
  private _disposed = false;

  private constructor(
    panel: vscode.WebviewPanel,
    private backendUrl: string,
  ) {
    this.panel = panel;
    this.panel.webview.html = this.getHtml(backendUrl);

    this.panel.onDidDispose(() => {
      this._disposed = true;
      ClarityWebviewPanel.instance = undefined;
    });
  }

  /**
   * Create or reveal the Clarity webview panel.
   */
  static createOrShow(backendUrl: string): ClarityWebviewPanel {
    // If we already have a panel, reveal it
    if (ClarityWebviewPanel.instance) {
      ClarityWebviewPanel.instance.panel.reveal(vscode.ViewColumn.One);
      // Update URL if backend restarted on a different port
      if (ClarityWebviewPanel.instance.backendUrl !== backendUrl) {
        ClarityWebviewPanel.instance.backendUrl = backendUrl;
        ClarityWebviewPanel.instance.panel.webview.html =
          ClarityWebviewPanel.instance.getHtml(backendUrl);
      }
      return ClarityWebviewPanel.instance;
    }

    // Otherwise create a new panel
    const panel = vscode.window.createWebviewPanel(
      ClarityWebviewPanel.viewType,
      "Clarity Agent",
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        // Allow the webview to access the local backend
        localResourceRoots: [],
      },
    );

    // Set the icon
    // panel.iconPath = ...;  // Could add an icon here

    const instance = new ClarityWebviewPanel(panel, backendUrl);
    ClarityWebviewPanel.instance = instance;
    return instance;
  }

  /**
   * Update the backend URL (e.g., after a restart).
   */
  updateUrl(backendUrl: string): void {
    this.backendUrl = backendUrl;
    if (!this._disposed) {
      this.panel.webview.html = this.getHtml(backendUrl);
    }
  }

  /**
   * Show a loading/error state while the backend is starting.
   */
  showStarting(): void {
    if (!this._disposed) {
      this.panel.webview.html = this.getLoadingHtml();
    }
  }

  /**
   * Show an error state.
   */
  showError(message: string): void {
    if (!this._disposed) {
      this.panel.webview.html = this.getErrorHtml(message);
    }
  }

  get disposed(): boolean {
    return this._disposed;
  }

  dispose(): void {
    this.panel.dispose();
  }

  private getHtml(backendUrl: string): string {
    return /* html */ `<!DOCTYPE html>
<html lang="en" style="height:100%;margin:0;padding:0;">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clarity Agent</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; overflow: hidden; background: #1a1a2e; }
    iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    .loading-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #1a1a2e;
      color: #a0a0b0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      z-index: 10;
      transition: opacity 0.3s;
    }
    .loading-overlay.hidden { opacity: 0; pointer-events: none; }
  </style>
</head>
<body>
  <div id="loading" class="loading-overlay">Loading Clarity Agent...</div>
  <iframe
    id="clarity-frame"
    src="${backendUrl}"
    allow="clipboard-read; clipboard-write; downloads"
    sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
  ></iframe>
  <script>
    const iframe = document.getElementById('clarity-frame');
    const loading = document.getElementById('loading');
    iframe.addEventListener('load', () => {
      loading.classList.add('hidden');
      setTimeout(() => loading.remove(), 500);
    });
    // If the iframe fails to load after 30s, show an error
    setTimeout(() => {
      if (!loading.classList.contains('hidden')) {
        loading.textContent = 'Failed to connect to Clarity backend. Check the output panel.';
      }
    }, 30000);
  </script>
</body>
</html>`;
  }

  private getLoadingHtml(): string {
    return /* html */ `<!DOCTYPE html>
<html lang="en" style="height:100%;margin:0;padding:0;">
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; }
    html, body {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #1a1a2e;
      color: #a0a0b0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .spinner {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }
    .dot-pulse {
      display: flex;
      gap: 6px;
    }
    .dot-pulse span {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #6c6c8a;
      animation: pulse 1.4s infinite ease-in-out both;
    }
    .dot-pulse span:nth-child(1) { animation-delay: -0.32s; }
    .dot-pulse span:nth-child(2) { animation-delay: -0.16s; }
    @keyframes pulse {
      0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }
  </style>
</head>
<body>
  <div class="spinner">
    <div class="dot-pulse"><span></span><span></span><span></span></div>
    <div>Starting Clarity Agent backend...</div>
  </div>
</body>
</html>`;
  }

  private getErrorHtml(message: string): string {
    const escaped = message
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    return /* html */ `<!DOCTYPE html>
<html lang="en" style="height:100%;margin:0;padding:0;">
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; }
    html, body {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #1a1a2e;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .error-box {
      max-width: 500px;
      text-align: center;
      padding: 32px;
    }
    .error-icon { font-size: 48px; margin-bottom: 16px; }
    h2 { color: #ff6b6b; margin-bottom: 12px; font-size: 18px; }
    p { color: #a0a0b0; font-size: 14px; line-height: 1.5; }
    code {
      display: block;
      margin-top: 16px;
      padding: 12px;
      background: #0d0d1a;
      border-radius: 6px;
      font-size: 12px;
      color: #ff9999;
      text-align: left;
      white-space: pre-wrap;
    }
    .hint {
      margin-top: 16px;
      color: #8080a0;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="error-box">
    <div class="error-icon">⚠️</div>
    <h2>Backend Error</h2>
    <p>The Clarity Agent backend could not start.</p>
    <code>${escaped}</code>
    <p class="hint">
      Run <strong>Clarity: Doctor</strong> from the Command Palette to diagnose,
      or check the <strong>Clarity Agent</strong> output panel.
    </p>
  </div>
</body>
</html>`;
  }
}