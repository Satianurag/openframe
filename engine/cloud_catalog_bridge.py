"""Read the hosted node catalog using the installed CLI's credential manager.

Executed with the CLI environment's Python. Credentials remain in that process;
only public node schemas leave it. No login, subscription or billing mutation.
"""
import json
import sys

from comfy_cli.target import resolve_target
from comfy_cli.command.cloud_http import http_request

try:
    target = resolve_target(where="cloud", allow_clear=False)
    if target.base_url.rstrip("/") != "https://cloud.comfy.org":
        raise ValueError("CLI session is not configured for hosted Comfy Cloud")
    status, catalog = http_request(target.url("object_info"), target, timeout=60, strict_json=True)
    if status != 200 or not isinstance(catalog, dict):
        raise ValueError("Cloud returned no node catalog")
    print(json.dumps(catalog))
except Exception as exc:
    # Never print a credential-bearing request, session or exception repr.
    print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
    sys.exit(1)
