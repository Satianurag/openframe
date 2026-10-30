"""Extract explicit media associations from the saved, rendered app DOMs."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "artifacts/reference/separate-apps"
DESTINATION = ROOT / "docs/reference-engine-apps.json"


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.parts = [], []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def text(self):
        return " ".join(self.parts + [child.text() for child in self.children]).strip()


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node("root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].parts.append(data.strip())


def read(name):
    parser = Parser()
    parser.feed((CAPTURES / name).read_text())
    return parser.root


def media(node, title, category=None):
    image = next((item for item in node.walk() if item.tag == "img" and item.attrs.get("src", "").startswith("https://")), None)
    video = next((item for item in node.walk() if item.tag == "video" and item.attrs.get("src", "").startswith("https://")), None)
    poster = video.attrs.get("poster") if video else None
    poster = poster or (image.attrs["src"] if image else None)
    if not image and not video:
        return None
    result = {"id": hashlib.sha256((poster or video.attrs["src"]).encode()).hexdigest()[:12], "title": title, "source_url": "https://higgsfield.ai/marketing-studio"}
    if poster:
        result["poster"] = poster
    if video:
        result["video"] = video.attrs["src"]
    if category:
        result["category"] = category
    return result


def main():
    output = json.loads(DESTINATION.read_text())
    marketing = {"hero": [], "presets": [], "styles": [], "banner": []}
    categories = {"styles": "Product shot", "ad-styles": "Ads", "marketplace-styles": "Marketplace", "ugc-styles": "UGC", "motion-styles": "Motion", "tiktok-styles": "TikTok"}
    base = read("firefox-marketing-styles-dom.txt")
    for node in base.walk():
        if node.tag == "button" and node.attrs.get("aria-label") in {"UGC", "Product shot", "Motion", "Ads", "Posters", "Marketplace", "TikTok"}:
            item = media(node, node.attrs["aria-label"], node.attrs["aria-label"])
            if item and item.get("video"):
                marketing["hero"].append(item)
        if node.tag == "a" and node.attrs.get("aria-label"):
            item = media(node, node.attrs["aria-label"])
            if item:
                label = node.text().removesuffix(item["title"]).strip()
                item["category"] = {"Product motion": "Motion", "UGC video": "UGC"}.get(label, label)
                marketing["presets"].append(item)
    for suffix, category in categories.items():
        filename = f"firefox-marketing-{suffix}-dom.txt"
        if not (CAPTURES / filename).exists():
            continue
        root = read(filename)
        dialog = next(node for node in root.walk() if node.attrs.get("role") == "dialog")
        for node in dialog.walk():
            if node.tag == "button" and node.attrs.get("aria-label"):
                item = media(node, node.attrs["aria-label"], category)
                if item:
                    marketing["styles"].append(item)
    output["apps"]["marketing-ads"] = marketing
    if (CAPTURES / "firefox-marketing-ad-reference-dom.txt").exists():
        dialog = next(node for node in read("firefox-marketing-ad-reference-dom.txt").walk() if node.attrs.get("role") == "dialog")
        item = media(dialog, "Ad Reference")
        if item:
            marketing["banner"].append(item)
    if (CAPTURES / "firefox-katana-dom.txt").exists():
        katana = {"hero": [], "banner": [], "presets": []}
        root = read("firefox-katana-dom.txt")
        for node in root.walk():
            if node.tag == "video":
                item = media(node, "Katana reference edit")
                if item:
                    item["source_url"] = "https://higgsfield.ai/katana"
                    katana["banner" if "banner" in item["video"] else "hero"].append(item)
            if node.tag == "button" and node.attrs.get("aria-label", "").startswith("View "):
                item = media(node, node.attrs["aria-label"][5:])
                if item:
                    item["source_url"] = "https://higgsfield.ai/katana"
                    katana["presets"].append(item)
        for filename in CAPTURES.glob("firefox-katana-*-dom.txt"):
            root = read(filename.name)
            selected = next((node.text() for node in root.walk() if node.tag == "button" and node.attrs.get("aria-pressed") == "true" and node.text() in {"Personalized edits", "Style transfer", "Motion transfer"}), None)
            if selected:
                for node in root.walk():
                    if node.tag == "button" and node.attrs.get("aria-label", "").startswith("View "):
                        item = media(node, node.attrs["aria-label"][5:], selected)
                        if item:
                            item["source_url"] = "https://higgsfield.ai/katana"
                            existing = next((value for value in katana["presets"] if value["id"] == item["id"]), None)
                            if existing:
                                existing["category"] = selected
                            else:
                                katana["presets"].append(item)
        detail_name = "codex-katana-preset-detail-dom.txt"
        if (CAPTURES / detail_name).exists():
            detail = read(detail_name)
            video = next((node.attrs["src"] for node in detail.walk() if node.tag == "source" and "/katana-presets/" in node.attrs.get("src", "") and node.attrs.get("type") == "video/mp4"), None)
            preset = next((item for item in katana["presets"] if item["title"] == "Industrial Style Lookbook"), None)
            if preset and video:
                preset["video"] = video
                preset["capture"] = detail_name
                preset["observed_dimensions"] = {"width": 1080, "height": 1920}
                preset["displayed_duration"] = "0:12"
        output["apps"]["katana"] = katana
    if (CAPTURES / "codex-genjutsu-default-dom.txt").exists():
        genjutsu = {"hero": [], "banner": [], "presets": [], "styles": [], "style_hero": []}
        root = read("codex-genjutsu-default-dom.txt")
        for node in root.walk():
            if node.tag == "video" and any(part in node.attrs.get("src", "") for part in ("genjutsu-intro", "model-preview")):
                item = media(node, "Genjutsu public reference")
                item["source_url"] = "https://higgsfield.ai/ai/video?model=genjutsu"
                genjutsu["banner" if "model-preview" in item["video"] else "hero"].append(item)
            if node.tag == "article":
                label = "Objects swap" if "Objects swap" in node.text() else "Motion transfer"
                item = media(node, label, label)
                if item:
                    item["source_url"] = "https://higgsfield.ai/ai/video?model=genjutsu"
                    genjutsu["presets"].append(item)
        root = read("codex-genjutsu-selected-style-dom.txt" if (CAPTURES / "codex-genjutsu-selected-style-dom.txt").exists() else "codex-genjutsu-styles-dom.txt")
        for node in root.walk():
            label = node.attrs.get("aria-label", "")
            if node.tag == "button" and label and label not in {"Apply style settings", "Change style"} and any(child.tag == "video" and "restyle-presets" in child.attrs.get("src", "") for child in node.walk()):
                item = media(node, label, "Style transfer")
                item["source_url"] = "https://higgsfield.ai/ai/video?model=genjutsu"
                genjutsu["styles"].append(item)
            if node.tag == "video" and "restyle-cover" in node.attrs.get("src", ""):
                item = media(node, "One video, any style")
                item["source_url"] = "https://higgsfield.ai/ai/video?model=genjutsu"
                genjutsu["style_hero"].append(item)
        output["apps"]["genjutsu"] = genjutsu
    if (CAPTURES / "codex-influencer-style-dialog-settled-dom.txt").exists():
        root = read("codex-influencer-style-dialog-settled-dom.txt")
        dialog = next(node for node in root.walk() if node.attrs.get("role") == "dialog")
        direct = {}
        for node in dialog.walk():
            label = node.attrs.get("aria-label", "")
            if node.tag == "button" and label and any(child.tag == "video" and "restyle-presets" in child.attrs.get("src", "") for child in node.walk()):
                item = media(node, label, "Style transfer")
                item["source_url"] = "https://higgsfield.ai/influencer"
                item["capture"] = "codex-influencer-style-dialog-settled-dom.txt"
                direct[label] = item
        observed = (CAPTURES / "firefox-influencer-motion-styles.txt").read_text()
        titles = re.findall(r"toggle button Description: ([^\n]+?), Value:", observed)
        shared = {item["title"]: item for item in output["apps"]["genjutsu"]["styles"]}
        styles = []
        for title in titles:
            if title in direct:
                styles.append(direct[title])
            elif title in shared:
                item = dict(shared[title])
                item["capture"] = "firefox-influencer-motion-styles.txt + codex-genjutsu-selected-style-dom.txt"
                item["association"] = "Exact visible style name; shared catalogue media. The first eleven modal styles have matching asset IDs."
                styles.append(item)
        output["apps"]["ai-influencer"]["styles"] = styles
    if (CAPTURES / "codex-popcorn-instadump-dom.txt").exists():
        root = read("codex-popcorn-instadump-dom.txt")
        popcorn = {"hero": [], "mobile_hero": [], "instadump_hero": [], "packs": []}
        for node in root.walk():
            if node.tag != "video":
                continue
            url = node.attrs.get("src", "")
            if not any(part in url for part in ("storyboard-empty-state", "instadump_notext")):
                continue
            key = "instadump_hero" if "instadump" in url else "mobile_hero" if "mobile" in url else "hero"
            item = media(node, "Instadump" if key == "instadump_hero" else "Popcorn storyboard")
            poster_marker = "instadump_notext.webp" if key == "instadump_hero" else "storyboard-empty-state.webp"
            poster = next((entry.attrs["src"] for entry in root.walk() if entry.tag == "img" and poster_marker in entry.attrs.get("src", "")), None)
            if poster:
                item["poster"] = poster
            item["source_url"] = "https://higgsfield.ai/storyboard"
            popcorn[key].append(item)
        output["apps"]["popcorn"] = popcorn
    urls = {item["url"] for item in output["assets"]}
    for app in (marketing, output["apps"].get("ai-influencer", {}), output["apps"].get("katana", {}), output["apps"].get("genjutsu", {}), output["apps"].get("popcorn", {})):
        for items in app.values():
            for item in items:
                urls.update(item[key] for key in ("poster", "video") if item.get(key))
    output["assets"] = [{"url": url, "download": True} for url in sorted(urls)]
    DESTINATION.write_text(json.dumps(output, indent=2) + "\n")
    print({key: len(value) for key, value in marketing.items()}, "unique assets", len(urls))


if __name__ == "__main__":
    main()
