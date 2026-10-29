"""Export portable API graphs and, with a live catalog, editable ComfyUI canvases."""
import argparse
import json
from pathlib import Path
import uuid
from .workflows import build_workflow


def to_ui_workflow(graph, catalog):
    """Use the installed node schemas rather than guessing widget ordering."""
    ids = {key: i + 1 for i, key in enumerate(graph)}
    links = []
    nodes = []
    depth_cache = {}
    def depth(key):
        if key in depth_cache:
            return depth_cache[key]
        parents = [value[0] for value in graph[key]["inputs"].values() if isinstance(value, list) and len(value) == 2 and value[0] in graph]
        depth_cache[key] = 1 + max((depth(p) for p in parents), default=-1)
        return depth_cache[key]
    rows = {}
    for key, spec in graph.items():
        cls = spec["class_type"]
        if cls not in catalog:
            raise ValueError(f"Install node class {cls} before exporting its editable canvas.")
        info = catalog[cls]
        schemas = {**info.get("input", {}).get("required", {}), **info.get("input", {}).get("optional", {})}
        order = info.get("input_order", {})
        names = list(order.get("required", info.get("input", {}).get("required", {}).keys())) + list(order.get("optional", info.get("input", {}).get("optional", {}).keys()))
        inputs, widgets = [], []
        for name in names:
            schema = schemas[name]
            kind = schema[0]
            options = schema[1] if len(schema) > 1 and isinstance(schema[1], dict) else {}
            is_widget = isinstance(kind, list) or kind in {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}
            value = spec["inputs"].get(name)
            is_link = isinstance(value, list) and len(value) == 2 and value[0] in graph
            if is_widget:
                fallback = (kind[0] if kind else "") if isinstance(kind, list) else {"INT": 0, "FLOAT": 0, "STRING": "", "BOOLEAN": False}.get(kind, "")
                fallback = options.get("default", fallback)
                widgets.append(fallback if is_link or value is None else value)
                # Seed controls are frontend-only widgets not present in the API schema.
                if options.get("control_after_generate"):
                    widgets.append("fixed")
                if options.get("image_upload"):
                    widgets.append("image")
            if is_link or not is_widget:
                input_type = "COMBO" if isinstance(kind, list) else kind
                slot = {"name": name, "type": input_type, "link": None}
                if is_widget:
                    slot["widget"] = {"name": name}
                if is_link:
                    link_id = len(links) + 1
                    slot["link"] = link_id
                    links.append([link_id, ids[value[0]], value[1], ids[key], len(inputs), input_type])
                inputs.append(slot)
        outputs = [{"name": name, "type": kind, "links": [], "slot_index": i} for i, (name, kind) in enumerate(zip(info.get("output_name", info.get("output", [])), info.get("output", [])))]
        col = depth(key)
        height = max(100, 80 + 28 * len(widgets))
        y = rows.get(col, 0); rows[col] = y + height + 80
        nodes.append({"id": ids[key], "type": cls, "pos": [col * 380, y], "size": [340, height], "flags": {}, "order": ids[key] - 1, "mode": 0, "inputs": inputs, "outputs": outputs, "properties": {"Node name for S&R": cls}, "widgets_values": widgets, "title": spec.get("_meta", {}).get("title", cls)})
    by_id = {node["id"]: node for node in nodes}
    for link in links:
        by_id[link[1]]["outputs"][link[2]]["links"].append(link[0])
    return {"id": str(uuid.uuid4()), "revision": 0, "last_node_id": len(nodes), "last_link_id": len(links), "nodes": nodes, "links": links, "groups": [], "config": {}, "extra": {"ds": {"scale": .6, "offset": [60, 60]}, "openframe": {"format": "editable", "source": "OpenFrame ComfyUI workflow pack"}}, "version": .4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("workflows"))
    parser.add_argument("--comfy-url", help="Read this ComfyUI node catalog to also export editable UI graphs")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    catalog = None
    if args.comfy_url:
        import httpx
        response = httpx.get(args.comfy_url.rstrip("/") + "/object_info", timeout=30)
        response.raise_for_status(); catalog = response.json()
    recipes = [
        ("ltx-fast-text", "ltx-0.9.8", "text-to-video", 49, 24),
        ("ltx-fast-image", "ltx-0.9.8", "image-to-video", 49, 24),
        ("ltx-23-text", "ltx-2.3", "text-to-video", 49, 24),
        ("ltx-23-inpaint", "ltx-2.3", "remove-object", 49, 24),
        ("wan-vace-inpaint", "wan-vace", "replace-object", 49, 16),
        ("wan-vace-restyle", "wan-vace", "restyle", 49, 16),
    ]
    for name, model, effect, frames, fps in recipes:
        request = {"model_id": model, "effect_id": effect, "prompt": "Cinematic natural footage of a sunlit courtyard, detailed stone textures, a gentle breeze moves the leaves, smooth camera movement.", "width": 512, "height": 288, "frames": frames, "fps": fps, "seed": 42}
        graph = build_workflow(request)
        (args.output / f"{name}.api.json").write_text(json.dumps(graph, indent=2) + "\n")
        if catalog:
            (args.output / f"{name}.ui.json").write_text(json.dumps(to_ui_workflow(graph, catalog), indent=2) + "\n")
    print(f"Exported {len(recipes)} API recipes" + (" and editable canvases" if catalog else "") + f" to {args.output}")

if __name__ == "__main__":
    main()
