"""Cache explicitly catalogued public reference media for the local design study.

The manifest contains observed URLs, never user uploads or browser credentials.
Downloads are bounded, deduplicated and reusable; no website scripts are run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {"static.higgsfield.ai", "static-public-media.higgsfield.ai", "cdn.higgsfield.ai", "assets.higgsfield.ai", "images.higgs.ai", "higgsfield.ai", "d2ol7oe51mr4n9.cloudfront.net", "d8j0ntlcm91z4.cloudfront.net", "d29nkk4626dxhc.cloudfront.net"}
EXTENSIONS = {"video/mp4": ".mp4", "video/webm": ".webm", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/avif": ".avif", "image/svg+xml": ".svg", "font/woff2": ".woff2"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/reference-assets.json")
    parser.add_argument("--max-file-mb", type=int, default=24)
    parser.add_argument("--max-total-mb", type=int, default=200)
    args = parser.parse_args()
    source = json.loads(args.manifest.read_text())
    output = ROOT / "frontend/public/reference-media"
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / "cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    total = 0
    failures = []
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        for entry in source["assets"]:
            url = entry["url"]
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
                raise ValueError("Reference URL is outside the observed public media hosts")
            old = cache.get(url)
            stem = hashlib.sha256(url.encode()).hexdigest()[:20]
            if not old:
                for saved in output.glob(stem + ".*"):
                    mime = next((kind for kind, suffix in EXTENSIONS.items() if suffix == saved.suffix), None)
                    if mime and saved.stat().st_size:
                        old = {"file": saved.name, "bytes": saved.stat().st_size, "sha256": hashlib.sha256(saved.read_bytes()).hexdigest(), "mime": mime}
                        cache[url] = old
                        break
            if old and (output / old["file"]).is_file():
                total += old["bytes"]
                continue
            if not entry.get("download", True):
                continue
            temporary = output / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".partial")
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    if response.url.host not in ALLOWED_HOSTS:
                        raise ValueError("Unexpected download redirect host")
                    mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if mime == "image/jpg":
                        mime = "image/jpeg"
                    suffix = EXTENSIONS.get(mime)
                    if not suffix:
                        raise ValueError(f"Unexpected reference media type: {mime}")
                    declared_size = int(response.headers.get("content-length", "0"))
                    if declared_size > args.max_file_mb * 1048576 or total + declared_size > args.max_total_mb * 1048576:
                        raise ValueError("Reference download size budget exceeded")
                    size = 0
                    digest = hashlib.sha256()
                    with temporary.open("wb") as f:
                        for chunk in response.iter_bytes(262144):
                            size += len(chunk)
                            if size > args.max_file_mb * 1048576 or total + size > args.max_total_mb * 1048576:
                                raise ValueError("Reference download size budget exceeded")
                            f.write(chunk)
                            digest.update(chunk)
                    name = temporary.stem + suffix
                    temporary.replace(output / name)
                    cache[url] = {"file": name, "bytes": size, "sha256": digest.hexdigest(), "mime": mime}
                    total += size
            except (httpx.HTTPError, ValueError) as exc:
                failures.append({"url": url, "error": str(exc)})
            finally:
                temporary.unlink(missing_ok=True)
    wordmark_source = source.get("apps", {}).get("soul-image", {}).get("wordmark_svg")
    if wordmark_source:
        parsed_svg = ET.fromstring(wordmark_source)
        # The captured wordmark contains paths only; do not carry webpage attributes into it.
        clean_svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", **{
            key: parsed_svg.attrib[key] for key in ("width", "height", "viewBox", "fill")
            if key in parsed_svg.attrib
        }})
        for node in parsed_svg.iter():
            if node.tag.rsplit("}", 1)[-1] == "path":
                ET.SubElement(clean_svg, "path", {key: value for key, value in node.attrib.items()
                    if key in {"d", "fill", "fill-rule", "clip-rule"} and "url(" not in value})
        wordmark = output / "soul-wordmark.svg"
        svg_text = ET.tostring(clean_svg, encoding="unicode")
        if not wordmark.exists() or wordmark.read_text() != svg_text:
            wordmark.write_text(svg_text)

    def localize(value):
        if isinstance(value, dict):
            return {k: v if k == "source_url" else localize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [localize(v) for v in value]
        if isinstance(value, str) and value in cache:
            return "/reference-media/" + cache[value]["file"]
        return value
    rendered = localize({"apps": source["apps"], "source": "Public Higgsfield reference examples; not OpenFrame-generated results."})
    for path, data in ((cache_path, cache), (output / "manifest.json", rendered), (output / "failures.json", failures)):
        text = json.dumps(data, indent=2) + "\n"
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
    print(json.dumps({"cached_files": len(cache), "cached_bytes": total, "failures": len(failures), "manifest": str(output / "manifest.json")}))


if __name__ == "__main__":
    main()
