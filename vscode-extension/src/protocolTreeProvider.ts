/**
 * Tree data provider for protocol documents.
 *
 * Fetches the protocol tree and packet status from the backend API
 * and renders them as a native VS Code tree view with staleness icons.
 */

import * as vscode from "vscode";
import type { BackendManager } from "./backendManager";

/** A file or directory in the protocol tree. */
interface ProtocolFile {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: ProtocolFile[];
}

/** Document status from packet-status API. */
interface DocStatus {
  document: string;
  status: "current" | "stale" | "empty" | "untracked";
  reason?: string;
}

const STATUS_ICONS: Record<string, string> = {
  current: "$(check)",
  stale: "$(warning)",
  empty: "$(circle-slash)",
  untracked: "$(question)",
};

export class ProtocolTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly filePath: string,
    public readonly isDirectory: boolean,
    public readonly status?: string,
    collapsibleState?: vscode.TreeItemCollapsibleState,
  ) {
    super(
      label,
      collapsibleState ??
        (isDirectory
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.None),
    );

    if (!isDirectory) {
      this.command = {
        command: "clarity.openProtocolDocument",
        title: "Open Document",
        arguments: [filePath],
      };
      this.contextValue = "protocolDocument";

      if (status) {
        const icon = STATUS_ICONS[status] || "";
        this.description = icon ? `${icon} ${status}` : status;
      }
    } else {
      this.contextValue = "protocolDirectory";
    }

    this.tooltip = filePath;
  }
}

export class ProtocolTreeProvider
  implements vscode.TreeDataProvider<ProtocolTreeItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    ProtocolTreeItem | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private _backend: BackendManager | undefined;
  private _tree: ProtocolFile[] = [];
  private _statusMap: Map<string, string> = new Map();

  setBackend(backend: BackendManager): void {
    this._backend = backend;
    this.refresh();
  }

  refresh(): void {
    this._fetchData().then(() => {
      this._onDidChangeTreeData.fire();
    });
  }

  getTreeItem(element: ProtocolTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: ProtocolTreeItem): ProtocolTreeItem[] {
    if (!element) {
      return this._buildItems(this._tree);
    }

    // Find the matching node in the tree
    const node = this._findNode(this._tree, element.filePath);
    if (node && node.children) {
      return this._buildItems(node.children);
    }
    return [];
  }

  private _buildItems(files: ProtocolFile[]): ProtocolTreeItem[] {
    return files.map((f) => {
      const status = this._statusMap.get(f.path);
      return new ProtocolTreeItem(
        f.name,
        f.path,
        f.type === "directory",
        status,
      );
    });
  }

  private _findNode(
    nodes: ProtocolFile[],
    targetPath: string,
  ): ProtocolFile | undefined {
    for (const node of nodes) {
      if (node.path === targetPath) {
        return node;
      }
      if (node.children) {
        const found = this._findNode(node.children, targetPath);
        if (found) {
          return found;
        }
      }
    }
    return undefined;
  }

  private async _fetchData(): Promise<void> {
    if (!this._backend || this._backend.state !== "running") {
      this._tree = [];
      this._statusMap.clear();
      return;
    }

    try {
      const treeResp = await this._backend.apiGet("/api/protocol/tree");
      const treeData = JSON.parse(treeResp);
      this._tree = treeData.tree || treeData.files || [];
    } catch {
      this._tree = [];
    }

    try {
      const statusResp = await this._backend.apiGet("/api/packet-status");
      const statusData = JSON.parse(statusResp);
      this._statusMap.clear();
      const docs: DocStatus[] = statusData.documents || statusData.report?.documents || [];
      for (const doc of docs) {
        this._statusMap.set(doc.document, doc.status);
      }
    } catch {
      this._statusMap.clear();
    }
  }
}