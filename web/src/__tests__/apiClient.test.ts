import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getProtocolTree,
  getDocument,
  getPacketStatus,
  getTranscripts,
  getTranscript,
  getPacketOptions,
  generatePacket,
  getSession,
  getModelProfile,
  setModelOverride,
  removeProject,
} from "../api/client";

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockClear();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

function blobResponse(content: string, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    blob: () => Promise.resolve(new Blob([content])),
    text: () => Promise.resolve(content),
  });
}

function errorResponse(status: number, body: string) {
  return Promise.resolve({
    ok: false,
    status,
    text: () => Promise.resolve(body),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("API client", () => {
  describe("fetchJson error handling", () => {
    it("throws on non-OK response with status and body", async () => {
      mockFetch.mockReturnValue(errorResponse(404, "Not found"));
      await expect(getSession()).rejects.toThrow("404: Not found");
    });
  });

  describe("Protocol endpoints", () => {
    it("getProtocolTree calls GET /api/protocol/tree", async () => {
      const tree = { exists: true, tree: [{ path: "goal/problem.md", name: "problem.md" }] };
      mockFetch.mockReturnValue(jsonResponse(tree));

      const result = await getProtocolTree();
      expect(mockFetch).toHaveBeenCalledWith("/api/protocol/tree", undefined);
      expect(result).toEqual(tree);
    });

    it("getDocument calls GET /api/protocol/document/{path}", async () => {
      const doc = { path: "goal/problem.md", content: "# Problem" };
      mockFetch.mockReturnValue(jsonResponse(doc));

      const result = await getDocument("goal/problem.md");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/protocol/document/goal/problem.md",
        undefined,
      );
      expect(result).toEqual(doc);
    });
  });

  describe("Packet Status endpoint", () => {
    it("getPacketStatus calls GET /api/packet-status", async () => {
      const data = { report: {}, decisions: {}, next_action: null };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getPacketStatus();
      expect(mockFetch).toHaveBeenCalledWith("/api/packet-status", undefined);
      expect(result).toEqual(data);
    });
  });

  describe("Transcript endpoints", () => {
    it("getTranscripts calls GET /api/transcripts", async () => {
      const data = { transcripts: [{ name: "session-1.md", modified: 12345 }] };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getTranscripts();
      expect(mockFetch).toHaveBeenCalledWith("/api/transcripts", undefined);
      expect(result).toEqual(data);
    });

    it("getTranscript calls GET /api/transcripts/{name}", async () => {
      const data = { name: "session-1.md", content: "# Transcript" };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getTranscript("session-1.md");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/transcripts/session-1.md",
        undefined,
      );
      expect(result).toEqual(data);
    });
  });

  describe("Packet endpoints", () => {
    it("getPacketOptions calls GET /api/packet/options", async () => {
      const data = {
        sources: [{ id: "problem", title: "Problem Statement" }],
        formats: ["markdown", "docx"],
        parts: [{ title: "Introduction", source_ids: ["problem"] }],
      };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getPacketOptions();
      expect(mockFetch).toHaveBeenCalledWith("/api/packet/options", undefined);
      expect(result).toEqual(data);
    });

    it("generatePacket sends POST with sections and format", async () => {
      mockFetch.mockReturnValue(blobResponse("# Packet content"));

      const result = await generatePacket(["problem", "solution"], "markdown");
      expect(mockFetch).toHaveBeenCalledWith("/api/packet/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sections: ["problem", "solution"], format: "markdown", view: null }),
      });
      expect(result).toBeInstanceOf(Blob);
    });

    it("generatePacket passes null sections for all", async () => {
      mockFetch.mockReturnValue(blobResponse("content"));

      await generatePacket(null, "docx");
      expect(mockFetch).toHaveBeenCalledWith("/api/packet/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sections: null, format: "docx", view: null }),
      });
    });

    it("generatePacket throws on error", async () => {
      mockFetch.mockReturnValue(errorResponse(400, "Bad request"));
      await expect(generatePacket([], "markdown")).rejects.toThrow("400: Bad request");
    });
  });

  describe("Session endpoint", () => {
    it("getSession calls GET /api/session", async () => {
      const data = {
        active: true,
        thread_id: "abc",
        process: null,
        project_dir: "/tmp/test",
        backend: "anthropic",
        model: "claude-sonnet",
        active_model: "claude-sonnet",
        active_tier: "default",
      };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getSession();
      expect(mockFetch).toHaveBeenCalledWith("/api/session", undefined);
      expect(result).toEqual(data);
    });
  });

  describe("Model profile endpoints", () => {
    it("getModelProfile calls GET /api/model-profile", async () => {
      const data = {
        tiers: { default: "claude-sonnet", deep: "claude-opus" },
        override: null,
        auto: true,
        active_model: "claude-sonnet",
        active_tier: "default",
      };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await getModelProfile();
      expect(mockFetch).toHaveBeenCalledWith("/api/model-profile", undefined);
      expect(result).toEqual(data);
    });

    it("removeProject sends DELETE to /api/projects/{id}", async () => {
      mockFetch.mockReturnValue(jsonResponse({ status: "removed" }));

      // Real ids are 8-char hex hashes; encodeURIComponent is a no-op
      // on those, but the wrapper still calls it defensively, so the
      // test passes a synthetic value to exercise the encoding path.
      const result = await removeProject("ab/cd ef");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/projects/ab%2Fcd%20ef",
        { method: "DELETE" },
      );
      expect(result).toEqual({ status: "removed" });
    });

    it("setModelOverride sends PUT with tier", async () => {
      const data = {
        tiers: {},
        override: "deep",
        auto: false,
        active_model: "claude-opus",
        active_tier: "deep",
      };
      mockFetch.mockReturnValue(jsonResponse(data));

      const result = await setModelOverride("deep");
      expect(mockFetch).toHaveBeenCalledWith("/api/model-profile/override", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier: "deep" }),
      });
      expect(result).toEqual(data);
    });
  });
});
