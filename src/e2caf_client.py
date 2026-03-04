from __future__ import annotations

import os
import requests
from dataclasses import dataclass
from typing import Any, Dict

DEFAULT_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

@dataclass
class E2CAFClient:
    base_url: str
    timeout: float = DEFAULT_TIMEOUT

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def health(self) -> Dict[str, Any]:
        r = requests.get(self._url("/health"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def query(self, sql: str) -> Dict[str, Any]:
        r = requests.post(self._url("/query"), json={"sql": sql}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def write(self, sql: str) -> Dict[str, Any]:
        r = requests.post(self._url("/write"), json={"sql": sql}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

def get_client() -> E2CAFClient:
    base_url = os.getenv("API_BASE_URL", "").strip()
    if not base_url:
        raise RuntimeError("Missing API_BASE_URL. Set it in .env or environment variables.")
    return E2CAFClient(base_url=base_url)
