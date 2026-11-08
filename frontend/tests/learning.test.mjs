import test from "node:test";
import assert from "node:assert/strict";
import { independentlyVerified, runLabel } from "../lib/learning.ts";

// Synthetic presentation-contract fixture; never an API or execution receipt.
const bound = () => ({
  id: "fixture", status: "verified",
  artifact_targets: { binding_sha256: "fixture-binding", source_sha256: "fixture-source" },
  verification: { verification: "verified", scope: "blender_bevel_v1", artifact: "fixture.blend",
    read_only_hash_unchanged: true, target_binding_sha256: "fixture-binding", source_sha256: "fixture-source" },
});

test("a matching independent source-bound result can display verified", () => {
  assert.equal(independentlyVerified(bound()), true);
});
for (const [name, change] of [
  ["source checking alone", run => { run.status = "source_checked"; }],
  ["GUI observation alone", run => { run.status = "observed_complete"; }],
  ["saved unverified artifact", run => { run.status = "saved_unverified"; }],
  ["failed artifact check", run => { run.verification.verification = "failed"; }],
  ["wrong target binding", run => { run.verification.target_binding_sha256 = "other"; }],
  ["no source hash anywhere", run => { delete run.verification.source_sha256; delete run.artifact_targets.source_sha256; }],
  ["wrong source binding", run => { run.verification.source_sha256 = "other"; }],
  ["legacy verification scope", run => { run.verification.scope = "legacy"; }],
  ["changed artifact hash", run => { run.verification.read_only_hash_unchanged = false; }],
  ["no saved artifact", run => { delete run.verification.artifact; }],
  ["no pre-execution targets", run => { delete run.artifact_targets; }],
]) {
  test(`${name} cannot display independent verification`, () => {
    const run = bound(); change(run);
    assert.equal(independentlyVerified(run), false);
  });
}
test("an approved copy is not shown as started", () => {
  assert.equal(runLabel("ready_for_review"), "Not started");
  assert.equal(independentlyVerified({ id: "fixture", status: "ready_for_review" }), false);
});
