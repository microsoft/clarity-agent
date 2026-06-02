/**
 * Webview view provider that displays the Clarity Agent React SPA
 * in the VS Code sidebar (Activity Bar panel).
 *
 * Uses an iframe pointing at the locally-running FastAPI backend,
 * which serves the same React app used by `clarity web`.
 */

import * as vscode from "vscode";
import {
  isOpenExternalMessage,
  OPEN_EXTERNAL_MESSAGE_TYPE,
  openExternalUrl,
} from "./externalLinks";

export interface WebviewMessage {
  command: string;
  [key: string]: unknown;
}

export class ClarityViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "clarity.sidebarView";

  private view?: vscode.WebviewView;
  private backendUrl = "";
  private _state: "idle" | "starting" | "running" | "error" = "idle";
  private _errorMessage = "";

  private readonly _onMessage = new vscode.EventEmitter<WebviewMessage>();
  /** Fires when the webview posts a message (e.g., the "Start" button). */
  public readonly onMessage = this._onMessage.event;

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this.view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [],
    };

    // Forward messages from webview to the event emitter
    webviewView.webview.onDidReceiveMessage((msg: WebviewMessage) => {
      if (isOpenExternalMessage(msg)) {
        void openExternalUrl(msg.url);
        return;
      }
      this._onMessage.fire(msg);
    });

    // Render current state
    this.render();

    webviewView.onDidDispose(() => {
      this.view = undefined;
    });
  }

  /**
   * Update the backend URL and switch to the running state.
   */
  updateUrl(backendUrl: string): void {
    this.backendUrl = backendUrl;
    this._state = "running";
    this.render();
  }

  /**
   * Show a loading/starting state.
   */
  showStarting(): void {
    this._state = "starting";
    this.render();
  }

  /**
   * Show an error state.
   */
  showError(message: string): void {
    this._state = "error";
    this._errorMessage = message;
    this.render();
  }

  /**
   * Reveal the sidebar view (brings it into focus).
   */
  reveal(): void {
    if (this.view) {
      this.view.show(true);
    } else {
      // If the view hasn't been resolved yet, focusing the view container
      // will trigger resolveWebviewView
      vscode.commands.executeCommand("clarity.sidebarView.focus");
    }
  }

  get isVisible(): boolean {
    return this.view?.visible ?? false;
  }

  // -----------------------------------------------------------------------
  // Rendering
  // -----------------------------------------------------------------------

  private render(): void {
    if (!this.view) {
      return;
    }

    switch (this._state) {
      case "running":
        this.view.webview.html = this.getAppHtml(this.backendUrl);
        break;
      case "starting":
        this.view.webview.html = this.getLoadingHtml();
        break;
      case "error":
        this.view.webview.html = this.getErrorHtml(this._errorMessage);
        break;
      default:
        this.view.webview.html = this.getIdleHtml();
        break;
    }
  }

  private getAppHtml(backendUrl: string): string {
    return /* html */ `<!DOCTYPE html>
<html lang="en" style="height:100%;margin:0;padding:0;">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clarity Agent</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; overflow: hidden; background: var(--vscode-editor-background, #1a1a2e); }
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
      background: var(--vscode-editor-background, #1a1a2e);
      color: var(--vscode-descriptionForeground, #a0a0b0);
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      font-size: 13px;
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
    const vscode = acquireVsCodeApi();
    const iframe = document.getElementById('clarity-frame');
    const loading = document.getElementById('loading');
    window.addEventListener('message', (event) => {
      if (event.source !== iframe.contentWindow) return;
      const message = event.data;
      if (!message || message.type !== '${OPEN_EXTERNAL_MESSAGE_TYPE}') return;
      vscode.postMessage(message);
    });
    iframe.addEventListener('load', () => {
      loading.classList.add('hidden');
      setTimeout(() => loading.remove(), 500);
    });
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
      background: var(--vscode-editor-background, #1a1a2e);
      color: var(--vscode-descriptionForeground, #a0a0b0);
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      font-size: 13px;
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
      background: var(--vscode-descriptionForeground, #6c6c8a);
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
      background: var(--vscode-editor-background, #1a1a2e);
      color: var(--vscode-editor-foreground, #e0e0e0);
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
    }
    .error-box {
      max-width: 100%;
      text-align: center;
      padding: 24px 16px;
    }
    .error-icon { font-size: 36px; margin-bottom: 12px; }
    h2 { color: var(--vscode-errorForeground, #ff6b6b); margin-bottom: 10px; font-size: 15px; }
    p { color: var(--vscode-descriptionForeground, #a0a0b0); font-size: 12px; line-height: 1.5; }
    code {
      display: block;
      margin-top: 12px;
      padding: 10px;
      background: var(--vscode-textCodeBlock-background, #0d0d1a);
      border-radius: 6px;
      font-size: 11px;
      color: var(--vscode-errorForeground, #ff9999);
      text-align: left;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .hint {
      margin-top: 12px;
      color: var(--vscode-descriptionForeground, #8080a0);
      font-size: 11px;
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

  private getIdleHtml(): string {
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
      background: var(--vscode-editor-background, #1a1a2e);
      color: var(--vscode-descriptionForeground, #a0a0b0);
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      font-size: 13px;
    }
    .idle-box {
      text-align: center;
      padding: 24px 16px;
    }
    .icon { font-size: 36px; margin-bottom: 12px; }
    h2 { 
      color: var(--vscode-editor-foreground, #e0e0e0);
      font-size: 15px; 
      margin-bottom: 8px; 
    }
    p { font-size: 12px; line-height: 1.5; margin-bottom: 16px; }
    button {
      background: var(--vscode-button-background, #0078d4);
      color: var(--vscode-button-foreground, #ffffff);
      border: none;
      padding: 8px 16px;
      border-radius: 4px;
      font-size: 12px;
      cursor: pointer;
      font-family: inherit;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground, #106ebe);
    }
  </style>
</head>
<body>
  <div class="idle-box">
    <div class="icon">💡</div>
    <h2>Clarity Agent</h2>
    <p>Structured thinking about what you're building, why, and what could go wrong.</p>
    <button id="start-btn">Start Clarity</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById('start-btn').addEventListener('click', () => {
      vscode.postMessage({ command: 'start' });
    });
  </script>
</body>
</html>`;
  }
}