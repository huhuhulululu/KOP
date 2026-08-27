from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from kop.config import HTTP_USER_AGENT


def get_bytes(url: str, timeout: float = 20.0, accept: str = "*/*", extra_headers: dict[str, str] | None = None) -> bytes:
    headers = {"User-Agent": HTTP_USER_AGENT, "Accept": accept}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GET {url} failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc


def get_text(url: str, timeout: float = 20.0) -> str:
    return get_bytes(url, timeout=timeout, accept="text/csv,text/plain,*/*").decode("utf-8")


def get_json(url: str, timeout: float = 20.0, extra_headers: dict[str, str] | None = None) -> Any:
    raw = get_bytes(url, timeout=timeout, accept="application/json", extra_headers=extra_headers)
    return json.loads(raw.decode("utf-8"))
