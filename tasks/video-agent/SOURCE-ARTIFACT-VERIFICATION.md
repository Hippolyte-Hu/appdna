# Source-bound Blender artifact verification

## Scope
Continue the accepted Holo4 learning receipt into a new PID-scoped scratch scene. Do not modify the accepted plan, user's scenes, legacy reference checks, other services, or Git publication state.

## Contract
- Support one explicit bounded inspector: `blender_bevel_v1`, a single cube mesh with one Bevel modifier and source-defined shading. Unsupported workflows stop or remain unverified; this is not an arbitrary Blender verifier.
- Holo4 derives final-state targets from original inspected images cited by the final accepted step, with the complete checked workflow as context. Required typed fields: shape, Bevel amount, segments, affect, width type, limit method, angle limit in degrees, smooth shading, and Smooth by Angle presence. No arbitrary Python, expressions or attribute paths are accepted.
- Every target must cite real evidence from that final interval. A separate Holo4 source request rechecks the whole target against original images; no previous model observations are substituted for images. Model source checking is not artifact verification.
- Bind the target receipt to actual source bytes, checked knowledge and exact parameters. Persist it before GUI execution, not after seeing the artifact. A modified execution plan cannot reuse an earlier target.
- Save through the existing real GUI executor, then inspect the saved `.blend` with a separate read-only Blender process and compare measured values with the pre-execution target. Check the artifact hash before/after inspection. Preserve measured/expected values and individual check results.
- Keep legacy checks for legacy jobs only. Never promote a new source on a legacy checker result; unbound results remain saved_unverified.

## Acceptance
1. RED/GREEN guards for typed values, source/citation binding, source rejection, changed plans/targets and wrong artifact values.
2. Real Holo4 target generation and original-image source check without manually editing values.
3. New scratch GUI execution under lock/PID/window/foreground guards; no existing scene reused.
4. Real saved artifact and independent read-only inspection, or an explicit blocked/failed receipt without a fabricated success.
5. API/UI display states and downloads match real receipts; test suite/compile/diff checks pass; disposable preview is stopped.

## Safe execution reuse
- The hard write boundary is a macOS Seatbelt profile: default read/runtime behavior, but deny all filesystem writes except the new, canonical `run` directory. No unsandboxed fallback. Python environment/config/cache/temp paths are private to this run; provider credentials are not inherited.
- Attach only with a matching PID/start identity, canonical scope, generated profile hash and live kernel write-permission checks. Existing directories must be queried: `sandbox_check` falsely reports denial for nonexistent paths even for an unsandboxed PID.
- Saving is directory-first, then filename, then confirmation; a real target file is required for completion. This sequence is a usability guard, not the filesystem security boundary.
- `POST /api/video-sources/{source_id}/executions` reuses source-checked knowledge without running download, ASR, learning or GUI actions. It creates a new job UUID, copies the checked source, plan, cited frames and valid pre-bound targets, but never copies run receipts, artifacts or approvals. Execution still requires explicit review and scratch approval.
- Execution jobs record `source_job_id`, do not appear as new learned sources, and show reuse in the English workbench. Preserve old jobs; unsupported/tampered/missing source evidence fails before creating a new execution.
