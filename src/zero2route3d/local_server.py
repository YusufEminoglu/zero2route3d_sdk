"""Localhost HTTP server for serving 02Route 3D WebGL Studio to QWebEngineView."""

from __future__ import annotations

import contextlib
import functools
import http.server
import mimetypes
import socket
import socketserver
import threading
from pathlib import Path
from typing import Optional


class QuietCorsHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP Request Handler with CORS headers and quiet logging."""

    def log_message(self, fmt: str, *args: object) -> None:
        return None

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()


class ReusableTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


class Route3DLocalServer:
    """Lightweight 127.0.0.1 HTTP server for serving WebGL ES-modules without file:// CORS blocks."""

    def __init__(
        self, web_root: Path, host: str = "127.0.0.1", start_port: int = 8920, end_port: int = 8950
    ) -> None:
        self.web_root = Path(web_root).resolve()
        if not self.web_root.is_dir():
            raise FileNotFoundError(f"WebGL assets directory does not exist: {self.web_root}")
        self.host = host
        self.start_port = max(0, min(65535, int(start_port)))
        self.end_port = max(self.start_port, min(65535, int(end_port)))
        self.port: Optional[int] = None
        self._httpd: Optional[ReusableTcpServer] = None
        self._thread: Optional[threading.Thread] = None

        mimetypes.add_type("application/javascript", ".js")
        mimetypes.add_type("application/json", ".geojson")
        mimetypes.add_type("text/css", ".css")
        mimetypes.add_type("text/html", ".html")

    @property
    def is_running(self) -> bool:
        return self._httpd is not None and self._thread is not None and self._thread.is_alive()

    @property
    def url(self) -> str:
        if self.port is None:
            return ""
        return f"http://{self.host}:{self.port}/index.html"

    def start(self) -> str:
        if self.is_running:
            return self.url

        handler = functools.partial(QuietCorsHandler, directory=str(self.web_root))
        for port in range(self.start_port, self.end_port + 1):
            if _port_is_open(self.host, port):
                continue
            try:
                self._httpd = ReusableTcpServer((self.host, port), handler)
                self.port = port
                break
            except OSError:
                continue

        if self._httpd is None:
            # Fallback to random free port assigned by OS
            self._httpd = ReusableTcpServer((self.host, 0), handler)
            self.port = self._httpd.server_address[1]

        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="Route3DServer", daemon=True
        )
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._httpd is None:
            return
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        self.port = None

        with contextlib.suppress(Exception):
            httpd.shutdown()
        with contextlib.suppress(Exception):
            httpd.server_close()
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
