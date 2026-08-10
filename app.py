#!/usr/bin/env python3
"""
Local Chat AI — Render / Railway / any host backend
Serves the chat UI and proxies OpenAI-compatible chat completions.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8787"))
UPSTREAM = os.environ.get("UPSTREAM", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.environ.get("API_KEY", os.environ.get("OPENAI_API_KEY", "")).strip()
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, direct technical assistant. Answer clearly and completely.",
)
ROOT = Path(__file__).resolve().parent
HTML_CANDIDATES = [
    ROOT / "public" / "index.html",
    ROOT / "index.html",
    ROOT / "public" / "LocalChatAI.html",
    ROOT / "LocalChatAI.html",
    Path.cwd() / "public" / "index.html",
    Path.cwd() / "index.html",
]


def find_html() -> Path:
    for p in HTML_CANDIDATES:
        if p.exists() and p.is_file():
            return p
    tried = ", ".join(str(p) for p in HTML_CANDIDATES)
    raise FileNotFoundError(
        "Missing UI file. Upload public/index.html (or index.html) next to app.py. "
        f"Tried: {tried}"
    )


def read_html() -> bytes:
    html_path = find_html()
    html = html_path.read_text(encoding="utf-8")
    # Inject server defaults so the browser starts ready on Render
    inject = (
        "<script>"
        f"window.__SERVER_DEFAULTS__={json.dumps({'baseUrl': '/v1', 'model': DEFAULT_MODEL, 'apiKey': 'server', 'systemPrompt': SYSTEM_PROMPT})};"
        "</script>"
    )
    if "</head>" in html:
        html = html.replace("</head>", inject + "\n</head>", 1)
    else:
        html = inject + html
    return html.encode("utf-8")


def proxy_chat(payload: dict, browser_key: str = "") -> tuple[int, dict | str]:
    if not isinstance(payload, dict):
        return 400, {"error": "Body must be a JSON object"}

    if not payload.get("model"):
        payload["model"] = DEFAULT_MODEL

    # Prefer server key; allow browser override only if server has no key
    key = API_KEY or browser_key or ""
    if not key or key in ("server", "ollama", "local", "none", "demo"):
        key = API_KEY
    if not key:
        return 401, {
            "error": "No API_KEY configured on the server. "
            "In Render: Environment → add API_KEY (or OPENAI_API_KEY)."
        }

    body = json.dumps(payload).encode("utf-8")
    url = f"{UPSTREAM}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"error": raw[:800]}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(err)
        except json.JSONDecodeError:
            return e.code, {"error": err[:800]}
    except urllib.error.URLError as e:
        return 502, {
            "error": f"Upstream unreachable: {e}",
            "upstream": UPSTREAM,
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalChatAI/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, code: int, obj) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/chat", "/app"):
            try:
                self._send(200, read_html(), "text/html; charset=utf-8")
            except FileNotFoundError as e:
                self._send(404, str(e).encode(), "text/plain; charset=utf-8")
            return

        if path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "upstream": UPSTREAM,
                    "default_model": DEFAULT_MODEL,
                    "api_key_set": bool(API_KEY),
                },
            )
            return

        if path == "/config":
            self._send_json(
                200,
                {
                    "baseUrl": "/v1",
                    "model": DEFAULT_MODEL,
                    "apiKeyRequired": not bool(API_KEY),
                    "apiKeySet": bool(API_KEY),
                },
            )
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        auth = self.headers.get("Authorization") or ""
        browser_key = ""
        if auth.lower().startswith("bearer "):
            browser_key = auth[7:].strip()

        code, result = proxy_chat(payload if isinstance(payload, dict) else {}, browser_key)
        if isinstance(result, (dict, list)):
            self._send_json(code, result)
        else:
            self._send(code, str(result).encode("utf-8"), "text/plain; charset=utf-8")


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 60)
    print("Local Chat AI")
    print(f"  listen:   {HOST}:{PORT}")
    print(f"  upstream: {UPSTREAM}")
    print(f"  model:    {DEFAULT_MODEL}")
    print(f"  api_key:  {'set' if API_KEY else 'MISSING — set API_KEY env var'}")
    print("=" * 60)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
