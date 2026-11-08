"""Import checked video knowledge into AppDNA's existing project/skill graph."""
import hashlib
import json
import shutil
from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.db import session_scope
from app.engines.packager import export_package
from app.models import Project,KnowledgeSource,KnowledgeClaim,Capability,Evidence
from app.store import Store
from app.util import utcnow
from app.agents.video_learning import write_json
_IMPORT_LOCK=Lock()


def package_video_project(db,project,folder):
    root=get_settings().artifacts_dir/project.id
    work=root/'run';work.mkdir(parents=True,exist_ok=True)
    evidence=root/'video-source';evidence.mkdir(exist_ok=True)
    relevance=root/'explore';relevance.mkdir(exist_ok=True)
    write_json(relevance/'source_relevance.json',{'checked':True,'sources':[{
        'id':'vsource_'+folder.name,'relevant':True,
        'summary':'Source-checked Blender video procedure. Source observations are not independent execution proof.'}]})
    for name in ('knowledge.json','plan.json','agent.json','transcript.json','artifact-expectations.json'):
        if (folder/name).is_file():shutil.copy2(folder/name,evidence/name)
    if (folder/'agent_frames').is_dir():shutil.copytree(folder/'agent_frames',evidence/'agent_frames',dirs_exist_ok=True)
    project.package_path=export_package(Store(db),project,work,root)
    db.commit()


def import_video_project(folder: Path) -> str:
    knowledge=json.loads((folder/'knowledge.json').read_text())
    plan=json.loads((folder/'plan.json').read_text())
    if knowledge.get('status')!='source_checked' or not knowledge.get('steps') or knowledge['steps']!=plan.get('steps'):
        raise ValueError('Only unchanged source-checked knowledge can be added to a project')
    source=folder/Path(knowledge.get('source_file','')).name
    if not source.is_file():raise ValueError('Original video evidence is missing')
    with source.open('rb') as handle:source_hash=hashlib.file_digest(handle,'sha256').hexdigest()
    if source_hash!=knowledge.get('source_sha256') or source_hash!=plan.get('source_sha256'):
        raise ValueError('Video source bytes do not match the accepted knowledge')
    project_id='video_'+folder.name
    source_id='vsource_'+folder.name
    with _IMPORT_LOCK,session_scope() as db:
        existing=db.get(Project,project_id)
        if existing is not None:
            relevance=get_settings().artifacts_dir/project_id/'explore/source_relevance.json'
            if not existing.package_path or not Path(existing.package_path).is_file() or not relevance.is_file():package_video_project(db,existing,folder)
            return project_id
        now=utcnow()
        project=Project(id=project_id,software_name='Blender',learning_objective=knowledge['objective'],
                       status='completed',created_at=now,updated_at=now)
        db.add(project)
        db.add(KnowledgeSource(id=source_id,project_id=project_id,title=knowledge['title'],
            url=knowledge.get('source_url') or f'/video/assets/{folder.name}/{source.name}',source_type='video',
            retrieved_at=now,content_reference=str(folder/'knowledge.json'),reliability='medium'))
        for i,step in enumerate(knowledge['steps']):
            claim_id=f'vc_{folder.name}_{i}'
            db.add(KnowledgeClaim(id=claim_id,project_id=project_id,claim=step['instruction'],
                claim_type='video_observation',evidence_ids_json=json.dumps([source_id,*step['evidence_ids']]),
                confidence=.5,verification_status='observed'))
            db.add(Capability(id=f'vs_{folder.name}_{i}',project_id=project_id,
                name=step['instruction'][:200],description=step['instruction'],
                preconditions_json=json.dumps(knowledge.get('prerequisites',[])),inputs_json=json.dumps(['Blender GUI']),
                expected_outputs_json=json.dumps([step['expected']]),related_claims_json=json.dumps([claim_id]),
                confidence=.5,verification_status='observed'))
        db.add(Evidence(id='video_'+folder.name,project_id=project_id,origin='video_learning_agent',kind='video_knowledge',
            summary='Source-checked video procedure; not independent execution proof.',
            payload_json=json.dumps({'source_sha256':source_hash,'steps':knowledge['steps'],
                                     'source_checks':knowledge.get('source_checks',[])}),
            artifact_path=str(folder/'knowledge.json'),created_at=now))
        db.commit()
        package_video_project(db,project,folder)
    return project_id
