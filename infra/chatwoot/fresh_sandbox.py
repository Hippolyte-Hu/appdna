"""Prepare a new Compose project without copying a database or routing rules."""

import argparse
import re
import secrets
from pathlib import Path

INFRA = Path(__file__).resolve().parent


def prepare(name: str, port: int, root: Path = INFRA) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,39}", name):
        raise ValueError("Use a unique lowercase sandbox name, 3–40 letters/digits/hyphens.")
    if not 1024 <= port <= 65535:
        raise ValueError("Use a local port between 1024 and 65535.")
    folder = root / "local" / name
    folder.mkdir(parents=True, mode=0o700)  # Refuse reuse rather than resetting old data.
    env = folder / ".env"
    password = secrets.token_urlsafe(24) + "-7aA!"
    values = {
        "APPDNA_COMPOSE_PROJECT": f"appdna-{name}",
        "APPDNA_CHATWOOT_PORT": str(port),
        "APPDNA_ENV_FILE": str(env.resolve()),
        "APPDNA_OUTPUT_DIR": str(folder.resolve()),
        "SECRET_KEY_BASE": secrets.token_hex(64),
        "FRONTEND_URL": f"http://127.0.0.1:{port}",
        "FORCE_SSL": "false", "ENABLE_ACCOUNT_SIGNUP": "false", "RAILS_LOG_TO_STDOUT": "true",
        "POSTGRES_HOST": "postgres", "POSTGRES_PORT": "5432", "POSTGRES_DATABASE": "chatwoot",
        "POSTGRES_USERNAME": "postgres", "POSTGRES_PASSWORD": secrets.token_hex(24),
        "REDIS_URL": "redis://redis:6379", "ACTIVE_STORAGE_SERVICE": "local",
        "APPDNA_ADMIN_EMAIL": "admin@northstar.invalid", "APPDNA_ADMIN_PASSWORD": password,
    }
    env.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    env.chmod(0o600)
    credentials = folder / "admin.txt"
    credentials.write_text(f"Local synthetic Chatwoot administrator\nEmail: admin@northstar.invalid\nPassword: {password}\n")
    credentials.chmod(0o600)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--port", type=int, default=3002)
    args = parser.parse_args()
    try:
        env = prepare(args.name, args.port)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    print(f"Prepared fresh project appdna-{args.name} on 127.0.0.1:{args.port}.")
    print(f"From infra/chatwoot, add --env-file {env.relative_to(INFRA)} to each docker compose command.")
    print("Run db:chatwoot_prepare, then the existing seed.rb, then up -d rails sidekiq.")
    print("Only supporting teams/inbox/admin are seeded. Automation rules are never copied or created.")


if __name__ == "__main__":
    main()
