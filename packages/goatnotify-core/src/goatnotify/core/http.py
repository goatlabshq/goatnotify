"""Minimal HTTP transport abstraction shared by webhook and HTTP-based email providers."""

import asyncio
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from goatnotify.core.errors import InvalidMessageError

ALLOWED_SCHEMES = frozenset({"http", "https"})


def require_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.netloc:
        raise InvalidMessageError("Only absolute http and https URLs are allowed")


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout: float


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        return next((v for k, v in self.headers.items() if k.lower() == wanted), None)


class HttpTransport(Protocol):
    async def send(self, request: HttpRequest) -> HttpResponse: ...


class UrllibTransport:
    """HttpTransport on urllib.request, run in a worker thread."""

    async def send(self, request: HttpRequest) -> HttpResponse:
        require_http_url(request.url)
        return await asyncio.to_thread(self._send, request)

    def _send(self, request: HttpRequest) -> HttpResponse:
        prepared = urllib.request.Request(  # noqa: S310 (scheme checked by require_http_url)
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            # Safe: send() has already restricted the URL to http and https.
            with urllib.request.urlopen(prepared, timeout=request.timeout) as response:  # noqa: S310 # nosemgrep
                return HttpResponse(
                    response.status, dict(response.headers.items()), response.read()
                )
        except urllib.error.HTTPError as error:
            with error:
                return HttpResponse(error.code, dict(error.headers.items()), error.read())
