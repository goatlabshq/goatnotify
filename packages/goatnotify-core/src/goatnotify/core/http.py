import asyncio
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import Message
from importlib.metadata import PackageNotFoundError, version
from typing import IO, Protocol, override
from urllib.parse import urlsplit

from goatnotify.core.errors import InvalidMessageError


def _distribution_version() -> str:
    try:
        return version("goatnotify-core")
    except PackageNotFoundError:
        return "unknown"


USER_AGENT = f"goatnotify/{_distribution_version()}"
ALLOWED_SCHEMES = frozenset({"http", "https"})


def require_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.netloc:
        raise InvalidMessageError("Only absolute http and https URLs are allowed")
    if not url.isascii() or not url.isprintable() or " " in url:
        raise InvalidMessageError("URLs must be percent-encoded ASCII without spaces")


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


def _with_user_agent(headers: Mapping[str, str]) -> dict[str, str]:
    # urllib's default "Python-urllib" agent is rejected by some bot-protected endpoints.
    if any(name.lower() == "user-agent" for name in headers):
        return dict(headers)
    return {**headers, "User-Agent": USER_AGENT}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib would replay a POST as a bodiless GET and forward signature headers to any host.
    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        return None


class UrllibTransport:
    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect)

    async def send(self, request: HttpRequest) -> HttpResponse:
        require_http_url(request.url)
        return await asyncio.to_thread(self._send, request)

    def _send(self, request: HttpRequest) -> HttpResponse:
        prepared = urllib.request.Request(  # noqa: S310 (scheme checked by require_http_url)
            request.url,
            data=request.body,
            headers=_with_user_agent(request.headers),
            method=request.method,
        )
        try:
            # Safe: send() has already restricted the URL to http and https.
            with self._opener.open(prepared, timeout=request.timeout) as response:  # nosemgrep
                return HttpResponse(
                    response.status, dict(response.headers.items()), response.read()
                )
        except urllib.error.HTTPError as error:
            with error:
                return HttpResponse(error.code, dict(error.headers.items()), error.read())
