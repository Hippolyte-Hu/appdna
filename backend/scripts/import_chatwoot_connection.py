"""Import only the local sandbox identifiers/token. Never print credentials."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
connection = json.loads((ROOT / "infra/chatwoot/local/connection.json").read_text())
env = ROOT / "backend/.env"
values = {"CHATWOOT_ACCOUNT_ID": str(connection["account_id"]), "CHATWOOT_INBOX_ID": str(connection["inbox_id"]),
          "CHATWOOT_API_TOKEN": connection["api_token"]}
lines = env.read_text().splitlines()
found = set()
for index, line in enumerate(lines):
    key = line.partition("=")[0]
    if key in values:
        lines[index] = f"{key}={values[key]}"
        found.add(key)
lines.extend(f"{key}={value}" for key, value in values.items() if key not in found)
env.write_text("\n".join(lines) + "\n")
env.chmod(0o600)
print("Imported the sandbox connection into backend/.env. Restart the backend to reload it.")
