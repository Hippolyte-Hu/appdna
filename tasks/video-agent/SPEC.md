# Video-taught Blender agent

Product: learn a bounded Blender workflow from a tutorial's audio and ordered images, then reproduce it through real GUI actions with H Company grounding on fresh screenshots.

Golden path: YouTube link or local video → FFmpeg audio + ordered frames → Gladia timed transcript → H Company evidence-linked step plan → user reviews → H Company screenshot/action loop → saved .blend → independent read-only bpy check.

First source candidate: https://www.youtube.com/watch?v=l12k19-imCY (Blender How to make cube round, blenderian, 168 seconds). First bounded task: replicate the first bevel-modifier workflow, not the later destructive alternative. Do not invent a material step absent from this source.

Execution boundaries: Blender only, designated fresh scratch scene only, no user work overwritten, no Python console/shell/code injection by the GUI agent, no external purchases or logins, no clicking security dialogs. Stop on screen lock or foreground mismatch. No direct bpy task execution; independent result inspection may use bpy. Save only inside this task's output folder, never overwrite an existing file.

Data contracts: plan has title, objective, prerequisites, steps (id, start, end, instruction, expected, uncertainty), limitations. Every step references the media timeline; model inferences are not verification. Execution log has fresh before/after screenshot paths and action payloads. Model completion is observed, not independently verified.

Slices: (1) media→validated plan + real provider run, (2) bounded GUI executor with lock/foreground guard and Stop control, (3) isolated browser UI with both inputs and step/evidence review, (4) real Blender repetition and independent artifact check. Preserve active LAN app; no restart or commit/push. Screen locked at preflight; GUI acceptance blocked until user unlocks.
