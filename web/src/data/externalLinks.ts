const VSCODE_OPEN_EXTERNAL_MESSAGE = "clarity.openExternal";

type PreventDefaultEvent = {
  preventDefault: () => void;
};

export function openExternalUrl(url: string, event?: PreventDefaultEvent): void {
  event?.preventDefault();
  const externalUrl = new URL(url, window.location.href).toString();

  if (window.parent !== window) {
    window.parent.postMessage(
      { type: VSCODE_OPEN_EXTERNAL_MESSAGE, url: externalUrl },
      "*",
    );
    return;
  }

  window.open(externalUrl, "_blank", "noopener,noreferrer");
}
