"""Bounded public product metadata import; no browser execution or link analysis agent."""
from __future__ import annotations

import concurrent.futures
import http.client
import hashlib
import io
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
import uuid
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from fastapi import HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .media import public_asset, register_asset

_DNS = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="product-dns")
_IMPORTS = threading.BoundedSemaphore(2)


class ProductImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=4096)


def _public_address(value):
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return _public_address(str(address.ipv4_mapped))
        if address.sixtofour or address.teredo or address in ipaddress.ip_network("64:ff9b::/96") or address in ipaddress.ip_network("64:ff9b:1::/48"):
            return False
    return True


def _destination(url, deadline):
    if any(ord(char) < 32 or ord(char) == 127 for char in url) or "\\" in url:
        raise ValueError("Use a normal public HTTP(S) URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Use a public HTTP(S) URL without credentials")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Product imports accept standard public web ports only")
    host = parsed.hostname.encode("idna").decode("ascii").rstrip(".")
    if "%" in host or host.lower() == "localhost" or host.lower().endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private and local network addresses cannot be imported")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("Product import exceeded its 30-second network budget")
    future = _DNS.submit(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    try:
        addresses = future.result(timeout=min(5, remaining))
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise ValueError("Product hostname lookup timed out") from exc
    unique = list(dict.fromkeys(item[4][0] for item in addresses))
    if not unique or any(not _public_address(address) for address in unique):
        raise ValueError("Private, loopback and link-local destinations cannot be imported")
    # The actual socket connects to this validated IP, never to a second DNS lookup.
    normalized_host = f"[{host}]" if ":" in host else host
    netloc = normalized_host + (f":{port}" if port != (443 if parsed.scheme == "https" else 80) else "")
    normalized = urlunsplit((parsed.scheme, netloc, quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~"), quote(parsed.query, safe="%=&?/:@!$'()*+,;~-._"), ""))
    return normalized, host, port, unique[0], parsed.scheme == "https"


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, secure, timeout):
        super().__init__(host, port=port, timeout=timeout)
        self.address, self.secure, self.active_socket = address, secure, None

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        self.active_socket = self.sock
        if self.secure:
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host, do_handshake_on_connect=False)
            self.active_socket = self.sock
            self.sock.do_handshake()

    def abort(self):
        if self.active_socket:
            try:
                self.active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.close()


def _fetch(url, limit, deadline, accept):
    for redirect in range(4):
        url, host, port, address, secure = _destination(url, deadline)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Product import exceeded its 30-second network budget")
        connection = _PinnedConnection(host, port, address, secure, min(10, remaining))
        timer = threading.Timer(remaining, connection.abort)
        timer.daemon = True
        timer.start()
        response = None
        try:
            parsed = urlsplit(url)
            connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers={
                "User-Agent": "OpenFrame-Product-Import/1.0", "Accept": accept,
                "Accept-Encoding": "identity", "Connection": "close",
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect == 3:
                    raise ValueError("The product URL redirects too many times")
                url = urljoin(url, location)
                if len(url) > 4096:
                    raise ValueError("The redirected URL is too long")
                continue
            if response.status != 200:
                raise ValueError(f"The website returned HTTP {response.status}")
            if response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise ValueError("The website ignored the uncompressed download request")
            length = response.getheader("Content-Length", "")
            if length.isdigit() and int(length) > limit:
                raise ValueError("The website response exceeds the import size limit")
            data = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("Product import exceeded its 30-second network budget")
                chunk = response.read1(min(65536, limit + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError("The website response exceeds the import size limit")
            return bytes(data), url, response.getheader("Content-Type", "").lower()
        finally:
            timer.cancel()
            if response:
                response.close()
            connection.abort()
    raise ValueError("The product URL redirects too many times")


class _Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self.scripts = {}, [], []
        self.in_title, self.script = False, None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key and values.get("content"):
                self.meta.setdefault(key, values["content"])
        elif tag == "title":
            self.in_title = True
        elif tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self.script = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.script is not None:
            if len(self.scripts) < 32:
                self.scripts.append("".join(self.script))
            self.script = None

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.script is not None:
            self.script.append(data)

    def product(self):
        queue, visited = [], 0
        for value in self.scripts:
            try:
                queue.append(json.loads(value))
            except (ValueError, RecursionError):
                pass
        while queue and visited < 2000:
            value = queue.pop()
            visited += 1
            if isinstance(value, list):
                queue.extend(value[:200])
            elif isinstance(value, dict):
                types = value.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if isinstance(types, list) and any(item in {"Product", "https://schema.org/Product", "http://schema.org/Product"} for item in types if isinstance(item, str)):
                    return value
                queue.extend(item for item in list(value.values())[:200] if isinstance(item, (dict, list)))
        return {}


def _text(value, limit):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", unescape(value if isinstance(value, str) else ""))).strip()[:limit]


def import_product(store, url):
    if not _IMPORTS.acquire(blocking=False):
        raise HTTPException(429, "Two product imports are already running; try again shortly")
    temporary = None
    try:
        deadline = time.monotonic() + 30
        page, source_url, content_type = _fetch(url.strip(), 2 * 1024 * 1024, deadline, "text/html,application/xhtml+xml")
        if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml+xml")):
            raise ValueError("This URL does not return an HTML product page")
        parser = _Metadata()
        parser.feed(page.decode("utf-8", errors="replace"))
        product = parser.product()
        title = _text(product.get("name") or parser.meta.get("og:title") or "".join(parser.title), 240) or urlsplit(source_url).hostname
        description = _text(product.get("description") or parser.meta.get("og:description") or parser.meta.get("description"), 5000)
        candidates = product.get("image", [])
        candidates = candidates if isinstance(candidates, list) else [candidates]
        candidates += [parser.meta.get(key) for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")]
        candidates = [value.get("url") or value.get("contentUrl") if isinstance(value, dict) else value for value in candidates]
        urls = list(dict.fromkeys(urljoin(source_url, value) for value in candidates if isinstance(value, str) and 0 < len(value) <= 4096))[:3]
        if not urls:
            raise ValueError("No Product/OG/Twitter image metadata was found")
        selected = None
        for image_url in urls:
            try:
                image_data, final_image_url, _ = _fetch(image_url, 12 * 1024 * 1024, deadline, "image/png,image/jpeg,image/webp")
                with Image.open(io.BytesIO(image_data)) as image:
                    if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 32_000_000 or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("Use a still PNG, JPEG or WebP product image below 32 megapixels")
                    suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image.format]
                    image.verify()
                selected = image_data, final_image_url, suffix
                break
            except (ValueError, OSError, http.client.HTTPException, Image.DecompressionBombError):
                continue
        if selected is None:
            raise ValueError("No readable public product image was available")
        data, image_url, suffix = selected
        asset = store.by_hash(hashlib.sha256(data).hexdigest())
        if not asset or not Path(asset["path"]).is_file():
            uploads = store.root / "uploads"
            uploads.mkdir(exist_ok=True, mode=0o700)
            temporary = uploads / f"{uuid.uuid4().hex}.product-import"
            temporary.write_bytes(data)
            asset = register_asset(store, temporary, f"{title[:160]}{suffix}", move=True)
        return {"title": title, "description": description, "source_url": source_url, "image_url": image_url,
                "asset": public_asset(asset), "warnings": ["Imported public page metadata and one image. Verify these details; no store, video or advertising analysis was performed."]}
    except (ValueError, OSError, http.client.HTTPException, Image.DecompressionBombError) as exc:
        raise HTTPException(422, f"Product import failed: {exc}. Upload the product image manually if this site blocks imports.") from exc
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        _IMPORTS.release()
