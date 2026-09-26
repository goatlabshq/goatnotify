import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from goatnotify.core.errors import InvalidMessageError
from goatnotify.core.http import HttpRequest, HttpResponse, UrllibTransport


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/moved":
            self.send_response(301)
            self.send_header("Location", "/ok")
            self.end_headers()
            return
        status = 500 if self.path == "/fail" else 200
        self.send_response(status)
        self.send_header("X-Echo", self.headers["X-Token"] or "")
        self.end_headers()
        self.wfile.write(body.upper())

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def base_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _request(url: str) -> HttpRequest:
    return HttpRequest(method="POST", url=url, headers={"X-Token": "t"}, body=b"ping", timeout=5)


async def test_a_successful_response(base_url: str) -> None:
    response = await UrllibTransport().send(_request(f"{base_url}/ok"))
    assert (response.status, response.body, response.header("x-echo")) == (200, b"PING", "t")


async def test_error_statuses_are_returned_not_raised(base_url: str) -> None:
    response = await UrllibTransport().send(_request(f"{base_url}/fail"))
    assert response.status == 500


async def test_only_http_urls_are_allowed() -> None:
    with pytest.raises(InvalidMessageError, match="http"):
        await UrllibTransport().send(_request("file:///etc/passwd"))


async def test_network_failures_raise_os_error() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(OSError, match=r"(?i)refused"):
        await UrllibTransport().send(_request(f"http://127.0.0.1:{port}/"))


def test_header_lookup_is_case_insensitive() -> None:
    assert HttpResponse(200, {"Retry-After": "5"}, b"").header("retry-after") == "5"


async def test_redirects_are_returned_not_followed(base_url: str) -> None:
    response = await UrllibTransport().send(_request(f"{base_url}/moved"))
    assert (response.status, response.header("Location")) == (301, "/ok")
