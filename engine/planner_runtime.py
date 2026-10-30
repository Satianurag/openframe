"""Isolated CUDA entry point; invoked only on the configured ComfyUI host."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    parser.add_argument("references")
    parser.add_argument("model_dir")
    parser.add_argument("output")
    args = parser.parse_args()
    from .planner import plan_local
    from .analysis_models import ANALYSIS_MODEL_ID
    request = json.loads(Path(args.request).read_text())
    references = json.loads(Path(args.references).read_text())
    result = plan_local(request, args.model_dir, model_id=ANALYSIS_MODEL_ID, references=references)
    output = json.dumps(result, ensure_ascii=False)
    if len(output.encode()) > 2 * 1024 * 1024:
        raise ValueError("The planner proposal exceeds its bounded result size.")
    Path(args.output).write_text(output)


if __name__ == "__main__":
    main()
