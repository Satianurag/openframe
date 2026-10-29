#!/usr/bin/env python3
"""Submit a saved OpenFrame recipe and download its real generated outputs."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path, help="JSON containing the job request or a saved job with a request field")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--mask", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--provider", choices=["local", "modal", "comfy-cloud"])
    parser.add_argument("--output", type=Path, default=Path("renders"))
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text())
    request = recipe.get("request", recipe)
    if args.provider:
        request["provider"] = args.provider
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as client:
        for field in ("source", "mask", "reference"):
            path = getattr(args, field)
            if path:
                with path.open("rb") as stream:
                    response = client.post("/api/assets", files={"file": (path.name, stream)})
                response.raise_for_status()
                request[field + "_asset_id"] = response.json()["id"]
        response = client.post("/api/jobs", json=request)
        response.raise_for_status()
        job = response.json()
        print(f"Job {job['id']}")
        for warning in job.get("warnings", []):
            print(f"Note: {warning}", file=sys.stderr)
        last_status = None
        try:
            while job["status"] not in {"succeeded", "failed", "cancelled"}:
                status = (job["status"], round(job.get("progress", 0) * 100), job.get("stage", ""))
                if status != last_status:
                    print(f"{status[0]} {status[1]}% — {status[2]}", flush=True)
                    last_status = status
                time.sleep(2)
                response = client.get(f"/api/jobs/{job['id']}")
                response.raise_for_status()
                job = response.json()
        except KeyboardInterrupt:
            response = client.post(f"/api/jobs/{job['id']}/cancel")
            response.raise_for_status()
            print("Cancellation requested.", file=sys.stderr)
            return 130
        if job["status"] != "succeeded":
            print(job.get("error") or job["status"], file=sys.stderr)
            return 1
        target = args.output / job["id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "job.json").write_text(json.dumps(job, indent=2) + "\n")
        for asset in job["outputs"]:
            destination = target / (asset["id"] + "-" + Path(asset["name"]).name)
            with client.stream("GET", asset["url"]) as result:
                result.raise_for_status()
                with destination.open("wb") as stream:
                    for chunk in result.iter_bytes(1024 * 1024):
                        stream.write(chunk)
            print(destination)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text[:1000]
        print(f"HTTP {exc.response.status_code}: {detail}", file=sys.stderr)
        raise SystemExit(1)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
