import assert from "node:assert/strict";
import test from "node:test";
import { formatAuditSummary } from "../src/format";
import { Audit } from "../src/types";

test("formatAuditSummary includes audit id, status, and per-tool scores", () => {
  const audit: Audit = {
    id: "audit-1",
    project_id: "project-1",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:01:00Z",
    results: [
      {
        tool: "meta_tags",
        status: "ok",
        score: 90,
        findings: [{ severity: "medium", code: "short_title", message: "Title too short" }],
        raw: {},
        progress: null,
        diff: null,
        created_at: "2026-01-01T00:01:00Z",
      },
    ],
  };

  const output = formatAuditSummary(audit);

  assert.match(output, /audit-1/);
  assert.match(output, /completed/);
  assert.match(output, /meta_tags/);
  assert.match(output, /score=90/);
  assert.match(output, /medium=1/);
});

test("formatAuditSummary handles a null score without printing 'null'", () => {
  const audit: Audit = {
    id: "audit-2",
    project_id: "project-1",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    completed_at: null,
    results: [
      {
        tool: "speed",
        status: "error",
        score: null,
        findings: [],
        raw: {},
        progress: null,
        diff: null,
        created_at: "2026-01-01T00:01:00Z",
      },
    ],
  };

  const output = formatAuditSummary(audit);

  assert.match(output, /score=n\/a/);
  assert.doesNotMatch(output, /null/);
});
