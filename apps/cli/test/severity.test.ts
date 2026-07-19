import assert from "node:assert/strict";
import test from "node:test";
import { hasFindingAtOrAbove, isValidSeverity } from "../src/severity";
import { Audit } from "../src/types";

function auditWith(findings: { severity: Audit["results"][number]["findings"][number]["severity"] }[]): Audit {
  return {
    id: "audit-1",
    project_id: "project-1",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:01:00Z",
    results: [
      {
        tool: "meta_tags",
        status: "ok",
        score: 80,
        findings: findings.map((f, i) => ({ ...f, code: `code_${i}`, message: "msg" })),
        raw: {},
        progress: null,
        diff: null,
        created_at: "2026-01-01T00:01:00Z",
      },
    ],
  };
}

test("hasFindingAtOrAbove is false when no findings meet the threshold", () => {
  const audit = auditWith([{ severity: "low" }, { severity: "info" }]);
  assert.equal(hasFindingAtOrAbove(audit, "high"), false);
});

test("hasFindingAtOrAbove is true when a finding matches the threshold exactly", () => {
  const audit = auditWith([{ severity: "high" }]);
  assert.equal(hasFindingAtOrAbove(audit, "high"), true);
});

test("hasFindingAtOrAbove is true when a finding is more severe than the threshold", () => {
  const audit = auditWith([{ severity: "critical" }]);
  assert.equal(hasFindingAtOrAbove(audit, "high"), true);
});

test("hasFindingAtOrAbove is false with no findings at all", () => {
  const audit = auditWith([]);
  assert.equal(hasFindingAtOrAbove(audit, "info"), false);
});

test("isValidSeverity accepts known severities and rejects unknown ones", () => {
  assert.equal(isValidSeverity("critical"), true);
  assert.equal(isValidSeverity("info"), true);
  assert.equal(isValidSeverity("urgent"), false);
});
