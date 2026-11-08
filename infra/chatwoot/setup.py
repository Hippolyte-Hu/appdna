"""Prepare ignored local configuration. No network calls or container mutations."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INFRA = Path(__file__).resolve().parent


def main():
    folder = INFRA / "local"
    folder.mkdir(exist_ok=True, mode=0o700)
    env = INFRA / ".env"
    if not env.exists():
        password = secrets.token_urlsafe(24) + "-7aA!"
        database_password = secrets.token_hex(24)
        values = {
            "SECRET_KEY_BASE": secrets.token_hex(64), "FRONTEND_URL": "http://127.0.0.1:3001",
            "FORCE_SSL": "false", "ENABLE_ACCOUNT_SIGNUP": "false", "RAILS_LOG_TO_STDOUT": "true",
            "POSTGRES_HOST": "postgres", "POSTGRES_PORT": "5432", "POSTGRES_DATABASE": "chatwoot",
            "POSTGRES_USERNAME": "postgres", "POSTGRES_PASSWORD": database_password,
            "REDIS_URL": "redis://redis:6379", "ACTIVE_STORAGE_SERVICE": "local",
            "APPDNA_ADMIN_EMAIL": "admin@northstar.invalid", "APPDNA_ADMIN_PASSWORD": password,
        }
        env.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
        env.chmod(0o600)
        credentials = folder / "admin.txt"
        credentials.write_text(f"Local synthetic Chatwoot administrator\nEmail: admin@northstar.invalid\nPassword: {password}\n")
        credentials.chmod(0o600)
    backend_env = ROOT / "backend" / ".env"
    if not backend_env.exists():
        backend_env.write_text((ROOT / "backend" / ".env.example").read_text().replace("CHATWOOT_TEST_ENVIRONMENT=false", "CHATWOOT_TEST_ENVIRONMENT=true"))
        backend_env.chmod(0o600)
    print("Prepared ignored environment files. Local login details: infra/chatwoot/local/admin.txt")
    print("Existing configuration was preserved. Start Docker, then follow infra/chatwoot/README.md.")


if __name__ == "__main__":
    main()
