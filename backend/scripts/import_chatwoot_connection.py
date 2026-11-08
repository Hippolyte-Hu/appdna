"""Import only the local sandbox identifiers/token. Never print credentials."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.connections import ChatwootConnection, save_values
from app.tasks import persistence as store
from pydantic import ValidationError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", type=Path, default=ROOT / "infra/chatwoot/local/connection.json")
    parser.add_argument("--url", help="Base address of the separately prepared synthetic sandbox")
    parser.add_argument("--session-path", help="Separate ignored browser state file for this sandbox")
    args = parser.parse_args()
    settings = get_settings()
    if settings.database_path.is_file() and any(t['latest_run'] and t['latest_run']['status'] not in store.TERMINAL
                                                for t in store.list_tasks()):
        parser.error("Wait for the active run to finish before switching sandbox connections.")
    try:
        connection = json.loads(args.connection.read_text())
        validated = ChatwootConnection(url=args.url or settings.chatwoot_base_url,
                                      account_id=connection["account_id"], inbox_id=connection["inbox_id"],
                                      api_token=connection["api_token"], test_environment=True)
    except (KeyError, ValueError, ValidationError):
        parser.error("The local synthetic connection file is incomplete or invalid.")
    values = {"CHATWOOT_ACCOUNT_ID": str(validated.account_id), "CHATWOOT_INBOX_ID": str(validated.inbox_id),
              "CHATWOOT_API_TOKEN": validated.api_token, "CHATWOOT_BASE_URL": validated.url,
              "CHATWOOT_TEST_ENVIRONMENT": "true"}
    if args.session_path:
        values["CHATWOOT_STORAGE_STATE"] = args.session_path
    elif args.url and validated.url != settings.chatwoot_base_url.rstrip("/"):
        parser.error("Use --session-path when switching to a different sandbox; existing sessions must stay isolated.")
    save_values(values)
    print("Imported only the synthetic sandbox connection. Existing model keys were preserved.")
    print("Refresh AppDNA Connections to reload settings, then sign in to the designated sandbox.")


if __name__ == "__main__":
    main()
