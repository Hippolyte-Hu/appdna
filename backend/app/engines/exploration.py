import json
from pathlib import Path

from app.adapters.blender import BlenderAdapter
from app.adapters.script_guard import ScriptRejected
from app.models import Capability, Experiment, Project
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import new_id, utcnow
from app.engines.learning import propose_experiment


async def explore_and_experiment(
    store: Store,
    project: Project,
    capability: Capability,
    blender: BlenderAdapter,
    reasoner: HCompanyProvider,
    workdir: Path,
) -> tuple[Experiment, dict | None]:
    initial = blender.inspect(workdir)
    store.add_evidence(
        project.id,
        origin="blender",
        kind="software_state",
        summary="Initial factory-startup scene",
        payload=initial,
        artifact_path=str(workdir / "inspect_stdout.log"),
    )
    store.log(
        project.id,
        "exploring",
        f"Inspected the startup scene ({len(initial.get('objects') or [])} objects).",
    )

    store.set_status(project, "experimenting")
    experiment = Experiment(
        id=new_id("experiment"),
        capability_id=capability.id,
        project_id=project.id,
        objective=project.learning_objective,
        actions_json="[]",
        observations_json="[]",
        result="pending",
        verification_status="discovered",
        created_at=utcnow(),
    )
    store.db.add(experiment)
    store.db.commit()

    feedback = None
    run = None
    for attempt in range(2):
        proposal = await propose_experiment(
            reasoner,
            project,
            capability,
            store.sources(project.id),
            feedback,
        )
        object_name = str(proposal.get("object_name") or "")
        material_name = str(proposal.get("material_name") or "")
        script = str(proposal.get("script") or "")
        experiment.object_name = object_name
        experiment.material_name = material_name
        experiment.objective = str(proposal.get("objective") or project.learning_objective)
        actions = json.loads(experiment.actions_json)
        actions.append(
            {
                "attempt": attempt + 1,
                "type": "bpy_script",
                "object_name": object_name,
                "material_name": material_name,
                "expected_result": proposal.get("expected_result"),
                "script": script,
            }
        )
        experiment.actions_json = json.dumps(actions)
        try:
            run = blender.run_experiment(script, workdir, object_name, material_name)
        except ScriptRejected as exc:
            feedback = str(exc)
            _observe(experiment, attempt, "rejected", feedback)
            store.add_evidence(
                project.id,
                origin="blender",
                kind="execution_log",
                summary=f"Experiment attempt {attempt + 1} rejected before execution",
                payload={"reason": feedback},
            )
            store.db.commit()
            continue
        if run["returncode"] != 0 or not run["blend_path"]:
            feedback = (run["stderr"] or run["stdout"] or "Blender did not write a scene file")[-1500:]
            _observe(experiment, attempt, "runtime_failure", feedback)
            store.add_evidence(
                project.id,
                origin="blender",
                kind="execution_log",
                summary=f"Experiment attempt {attempt + 1} failed in Blender",
                payload={"returncode": run["returncode"], "stderr": feedback},
                artifact_path=str(workdir / "experiment_stderr.log"),
            )
            store.db.commit()
            run = None
            continue
        _observe(experiment, attempt, "executed", run["stdout"][-500:])
        experiment.result = "success"
        experiment.verification_status = "experimented"
        capability.verification_status = "experimented"
        store.add_evidence(
            project.id,
            origin="blender",
            kind="generated_file",
            summary="Scene file written by the experiment script",
            payload={"returncode": run["returncode"], "blend_path": run["blend_path"]},
            artifact_path=run["blend_path"],
        )
        store.db.commit()
        store.log(project.id, "experimenting", f"Attempt {attempt + 1} wrote a scene file.")
        return experiment, run

    experiment.result = "failure"
    store.db.commit()
    store.log(project.id, "experimenting", "Both experiment attempts failed. The failure was kept.")
    return experiment, None


def _observe(experiment: Experiment, attempt: int, status: str, detail: str) -> None:
    observations = json.loads(experiment.observations_json)
    observations.append({"attempt": attempt + 1, "status": status, "detail": detail[:1500]})
    experiment.observations_json = json.dumps(observations)
