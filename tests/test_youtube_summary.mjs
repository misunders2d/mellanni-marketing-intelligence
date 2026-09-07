import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  summarizeManifest,
  summarizeVideo,
} from "../scripts/youtube-summary.mjs";

function manifest(items) {
  return {
    schema_version: 2,
    run_id: "test-run",
    exit_code: 0,
    source_failures: 0,
    youtube_item_count: items.length,
    items,
  };
}

function item(index) {
  return {
    item_id: `item-${index}`,
    source_slug: "ampmpodcast",
    source_name: "AM/PM Podcast",
    title: `Episode ${index}`,
    url: `https://www.youtube.com/watch?v=episode${index}`,
    published_at: "2026-09-07T00:00:00Z",
  };
}

function successfulResult(url) {
  return {
    text: `Detailed findings for ${url}`,
    model: "gemini-test",
    processing: "agentic",
    evidence: {
      processingCall: true,
      processingResult: true,
      agenticProcessingUsed: true,
    },
    attempts: [{ model: "gemini-test", status: "succeeded" }],
  };
}

test("batch writes one distinct artifact pair for every manifest video", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mmi-youtube-"));
  try {
    const manifestPath = path.join(root, "manifest.json");
    const outputDir = path.join(root, "youtube");
    await writeFile(manifestPath, JSON.stringify(manifest([item(1), item(2), item(3)])));
    const calls = [];
    const batch = await summarizeManifest({
      manifestPath,
      outputDir,
      summarizer: async ({ url }) => {
        calls.push(url);
        return successfulResult(url);
      },
    });

    assert.equal(batch.expected, 3);
    assert.equal(batch.succeeded, 3);
    assert.equal(batch.failed, 0);
    assert.equal(new Set(calls).size, 3);
    assert.equal(new Set(batch.results.map((row) => row.markdown_path)).size, 3);
    for (const row of batch.results) {
      assert.match(await readFile(row.markdown_path, "utf8"), /Detailed findings/);
    }
    const updated = JSON.parse(await readFile(manifestPath, "utf8"));
    assert.deepEqual(updated.youtube_summary, {
      status: "succeeded",
      expected: 3,
      succeeded: 3,
      failed: 0,
      manifest_path: path.join(outputDir, "youtube-summary-manifest.json"),
    });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("one video failure keeps successful artifacts and blocks digest", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mmi-youtube-"));
  try {
    const manifestPath = path.join(root, "manifest.json");
    const outputDir = path.join(root, "youtube");
    await writeFile(manifestPath, JSON.stringify(manifest([item(1), item(2)])));
    const batch = await summarizeManifest({
      manifestPath,
      outputDir,
      summarizer: async ({ url }) => {
        if (url.endsWith("episode2")) throw new Error("provider failed");
        return successfulResult(url);
      },
    });

    assert.equal(batch.succeeded, 1);
    assert.equal(batch.failed, 1);
    assert.match(batch.failures[0].error, /provider failed/);
    await readFile(batch.results[0].markdown_path, "utf8");
    const updated = JSON.parse(await readFile(manifestPath, "utf8"));
    assert.equal(updated.youtube_summary.status, "failed");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("fallback success retains failed primary attempt", async () => {
  const result = await summarizeVideo({
    url: "https://www.youtube.com/watch?v=episode",
    models: ["gemini-3.8-flash", "gemini-3.7-flash"],
    caller: async (model) => {
      if (model === "gemini-3.8-flash") throw new Error("primary unavailable");
      return {
        status: "completed",
        steps: [
          { type: "processing_call" },
          { type: "processing_result" },
          { type: "model_output", content: [{ type: "text", text: "Full result" }] },
        ],
      };
    },
  });
  assert.equal(result.model, "gemini-3.7-flash");
  assert.deepEqual(result.attempts.map((row) => row.status), ["failed", "succeeded"]);
  assert.match(result.attempts[0].error, /primary unavailable/);
});

test("agentic mode fails without processing evidence", async () => {
  await assert.rejects(
    summarizeVideo({
      url: "https://www.youtube.com/watch?v=episode",
      models: ["gemini-3.8-flash"],
      caller: async () => ({
        status: "completed",
        steps: [
          { type: "model_output", content: [{ type: "text", text: "Unverified result" }] },
        ],
      }),
    }),
    /lacked required agentic processing evidence/,
  );
});

test("failed collection manifest cannot start video processing", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mmi-youtube-"));
  try {
    const manifestPath = path.join(root, "manifest.json");
    const value = manifest([item(1)]);
    value.exit_code = 2;
    value.source_failures = 1;
    await writeFile(manifestPath, JSON.stringify(value));
    let called = false;
    await assert.rejects(
      summarizeManifest({
        manifestPath,
        outputDir: path.join(root, "youtube"),
        summarizer: async () => {
          called = true;
          return successfulResult("unused");
        },
      }),
      /Refusing YouTube batch from failed collection manifest/,
    );
    assert.equal(called, false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
