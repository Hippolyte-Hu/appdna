# Video learning validation — 2026-11-08

Branch: `codex/video-learning-fixes`, based on `feat/appdna-video-learning-agent` at `4aa58ed`.

The repository Blender example completed video learning, real GUI execution, GUI save to the exact isolated destination, and independent artifact inspection. The browser then downloaded the actual artifact and checked its hash, imported the learned procedure into the project/skill graph, and downloaded the ZIP package.

Machine-readable evidence summary: [video-learning-validation.json](video-learning-validation.json). Raw media, credentials, screenshots, transcript, receipts and `.blend` files remain in ignored local storage.

## Verification results

| Boundary | Evidence |
| --- | --- |
| Backend regression | 220 passed, 0 failed; one Starlette/AnyIO dependency deprecation warning |
| Frontend | Type checking and production build passed |
| Input → transcription | Browser-uploaded repository example; real Gladia transcription, 41 timestamped segments |
| Source learning | Holo4-27B, 7 decisions, 10 inspected frames, 5 accepted source-checked steps |
| Knowledge → computer use | Checked knowledge reused in a new sandboxed Blender process and factory scene; 15 screenshot-grounded decisions |
| GUI save | 5 decisions; file browser closed and titlebar showed `replica.blend` |
| Independent inspection | Separate Blender 5.1.2 process reopened the exact file; all 11 checks passed |
| Artifact integrity | 102,892 bytes; hash unchanged by inspection and matched the browser download |
| Project integration | 5 observed video capabilities, one matched source, working skill graph and ZIP download |
| Responsive browser | No page errors or horizontal overflow at 390 px in the workbench and project view |

Learning receipt: `a6f51c86c0224cebb84118204d1debf6`. Its source knowledge remained accepted when its early desktop attempt was blocked. Final execution receipt: `be93121b8cd74b04ae4e68ec6aab64f9`.

The accepted plan and parameters were not edited manually. The source was downloaded from the [repository example tutorial](https://www.youtube.com/watch?v=l12k19-imCY), then uploaded through the real UI to exercise Gladia. The final execution reused accepted source knowledge and media; previous scenes and execution receipts were not copied into its run directory.

## Expected and measured artifact

| Property | Expected | Measured |
| --- | --- | --- |
| Shape | Cube base mesh | Cube base mesh |
| Bevel affect | EDGES | EDGES |
| Width type | OFFSET | OFFSET |
| Width | 0.24 m | 0.2399999946 m |
| Segments | 4 | 4 |
| Limit method | ANGLE | ANGLE |
| Angle | 30° | 30.00000083° |
| Smooth shading | Enabled | Enabled |
| Smooth by Angle | Present | Present |
| Visible Bevel / rounded evaluated geometry | Present | Present |

Artifact SHA-256: `93b53945e12003859aa91966592d5a0c37ce19cad9418835f99f856c843b3a65`.

Source SHA-256: `f6f97d1deda194ad61b4434aea6952ab2fea26fd289d5a5da0e6e2ee9be182cf`.

## Repairs exercised

- OS-enforced per-run write confinement. Real Python child-process/symlink probes and a real headless Blender save probe preserved an existing outside file while allowing a save inside the run directory.
- Live-process attestation for resume; direct construction, stale PID files, changed plans and another scratch directory cannot authorize control.
- Resumable checkpoints for transient provider failures and lost foreground. Completed steps, capture history and cumulative action budgets survive resume. Stop and shutdown close the owned scratch process. Controller restart invalidates resume.
- Explicit desktop permission preflight and useful launch diagnostics; fresh worktrees can compile the helper without a pre-existing evidence directory.
- Startup Quick Setup versus ordinary splash handling, fresh-capture feedback and repeated-action protection.
- Bounded 90-second action inference requests and a bounded provider retry. Authentication failures remain terminal.
- Exact-destination save gates, source-bound measurements, fresh audit receipts and a nonzero exit code for inspector script failures. A stale audit cannot substitute for a failed inspection.
- Same-origin main-app integration, source caption fallback/uploads, independent model settings, truthful stop/restart states, knowledge reuse, project graphs and downloadable packages.
- Blender discovery for a standard macOS application installation, the missing retained localization helper, and matching browser dependencies.

## Earlier live failures and limits

Earlier retained attempts exposed missing desktop activation/permission, repeated splash input, foreground loss, and provider timeouts during ordinary actions and saving. These attempts remained blocked or artifact-failed. Their IDs and reasons are retained in the JSON summary; they were not promoted to success.

The final successful run needed no pause/resume intervention. Resume behavior has deterministic regression coverage, including preservation of completed steps and failed-request captures, budget retention, refusal of unattested processes, stop cleanup, and inspection of a file already saved before a model timeout.

This is one fresh source-learning success and one complete source-bound artifact success, with earlier failures disclosed. It is not a reliability estimate. Native control currently supports Blender on macOS, and independent inspection supports `blender_bevel_v1`; arbitrary applications and artifact types need additional adapters and outcome tests. Video source checks remain model observations. The independent result is scoped to the measured saved artifact.
