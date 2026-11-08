"""CLI safety regression tests; all provider and GUI work is forbidden/stubbed."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


def load_cli():
    spec=importlib.util.spec_from_file_location('tutorial_cli',Path(__file__).with_name('run_blender_tutorial.py'))
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_cli_rejects_cross_job_resume_before_any_gui(tmp_path,monkeypatch):
    module=load_cli()
    args=SimpleNamespace(job=tmp_path,model='holo4-27b',resume_from=tmp_path/'old',save_only=True)
    monkeypatch.setattr(argparse.ArgumentParser,'parse_args',lambda self:args)
    monkeypatch.setattr(module.BlenderTutorialDriver,'launch',lambda *a:pytest.fail('No GUI for cross-job PID attachment'))
    with pytest.raises(ValueError,match='resume is disabled'):asyncio.run(module.main())


def test_cli_source_target_rejection_precedes_blender_launch(tmp_path,monkeypatch):
    module=load_cli()
    args=SimpleNamespace(job=tmp_path,model='holo4-27b',resume_from=None,save_only=False)
    (tmp_path/'plan.json').write_text(json.dumps({'steps':[]}))
    (tmp_path/'knowledge.json').write_text('{}')
    monkeypatch.setattr(argparse.ArgumentParser,'parse_args',lambda self:args)
    monkeypatch.setattr(module,'get_settings',lambda:SimpleNamespace(hcompany_api_key='',hcompany_base_url=''))
    monkeypatch.setattr(module,'HCompanyProvider',lambda *a:SimpleNamespace(model='holo4-27b'))
    async def rejected(*args):raise ValueError('source targets rejected')
    monkeypatch.setattr(module,'build_expectations',rejected)
    monkeypatch.setattr(module.BlenderTutorialDriver,'launch',lambda *a:pytest.fail('No GUI before source-bound targets'))
    with pytest.raises(ValueError,match='source targets rejected'):asyncio.run(module.main())
    assert not (tmp_path/'run').exists()
