import importlib.util
import stat
from pathlib import Path

import pytest


path = Path(__file__).resolve().parents[2] / "infra/chatwoot/fresh_sandbox.py"
spec = importlib.util.spec_from_file_location("fresh_sandbox", path)
fresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)


def test_fresh_profiles_have_independent_projects_credentials_and_ports(tmp_path):
    first = fresh.prepare("reuse-check", 3002, tmp_path)
    second = fresh.prepare("cold-check", 3003, tmp_path)
    def values(path):
        return dict(line.split("=", 1) for line in path.read_text().splitlines())
    a, b = values(first), values(second)
    assert a['APPDNA_COMPOSE_PROJECT'] != b['APPDNA_COMPOSE_PROJECT']
    assert a['APPDNA_OUTPUT_DIR'] != b['APPDNA_OUTPUT_DIR']
    assert a['POSTGRES_PASSWORD'] != b['POSTGRES_PASSWORD']
    assert a['SECRET_KEY_BASE'] != b['SECRET_KEY_BASE']
    assert a['FRONTEND_URL'] == 'http://127.0.0.1:3002'
    assert b['FRONTEND_URL'] == 'http://127.0.0.1:3003'
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    assert not list(tmp_path.rglob('*.sql'))  # No source database/rules are copied.


def test_preparation_refuses_to_reset_an_existing_profile(tmp_path):
    env = fresh.prepare('reuse-check', 3002, tmp_path)
    original = env.read_bytes()
    with pytest.raises(FileExistsError):
        fresh.prepare('reuse-check', 3003, tmp_path)
    assert env.read_bytes() == original


@pytest.mark.parametrize('name,port', [('../escape', 3002), ('reuse-check', 80)])
def test_invalid_profile_never_creates_output(tmp_path, name, port):
    with pytest.raises(ValueError):
        fresh.prepare(name, port, tmp_path)
    assert list(tmp_path.iterdir()) == []
