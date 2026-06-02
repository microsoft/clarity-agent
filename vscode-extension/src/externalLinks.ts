import * as vscode from "vscode";

export const OPEN_EXTERNAL_MESSAGE_TYPE = "clarity.openExternal";

const ALLOWED_EXTERNAL_SCHEMES = new Set(["http", "https"]);

type OpenExternalMessage = {
  type: typeof OPEN_EXTERNAL_MESSAGE_TYPE;
  url?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isOpenExternalMessage(message: unknown): message is OpenExternalMessage {
  return isRecord(message) && message.type === OPEN_EXTERNAL_MESSAGE_TYPE;
}

export async function openExternalUrl(rawUrl: unknown): Promise<void> {
  if (typeof rawUrl !== "string") {
    await vscode.window.showWarningMessage("Clarity blocked an invalid external link.");
    return;
  }

  let uri: vscode.Uri;
  try {
    uri = vscode.Uri.parse(rawUrl, true);
  } catch {
    await vscode.window.showWarningMessage("Clarity blocked an invalid external link.");
    return;
  }

  if (!ALLOWED_EXTERNAL_SCHEMES.has(uri.scheme.toLowerCase())) {
    await vscode.window.showWarningMessage("Clarity blocked a non-web external link.");
    return;
  }

  const opened = await vscode.env.openExternal(uri);
  if (!opened) {
    await vscode.window.showWarningMessage("Clarity could not open the external link.");
  }
}
