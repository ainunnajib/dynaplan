import json
from typing import Any, Dict, Optional

import httpx


class DynaplanApiError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__("%s: %s" % (status_code, message))


class DynaplanClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key}

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return self.base_url + path
        return self.base_url + "/" + path

    def _extract_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            payload = None

        if isinstance(payload, dict):
            detail = payload.get("detail")
            error = payload.get("error")
            if isinstance(detail, str) and detail:
                return detail
            if isinstance(error, str) and error:
                return error

        text = response.text.strip()
        if text:
            return text
        return "Request failed"

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = httpx.request(
            method=method.upper(),
            url=self._build_url(path),
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs,
        )
        if response.status_code >= 400:
            raise DynaplanApiError(response.status_code, self._extract_error(response))
        return response

    def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.request(method, path, **kwargs)
        if len(response.content) == 0:
            return None
        return response.json()

    def request_bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        response = self.request(method, path, **kwargs)
        return response.content

