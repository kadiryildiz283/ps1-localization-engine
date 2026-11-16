"""COOP/COEP (SharedArrayBuffer) ve HTTP Range destekli yerel geliştirme sunucusu."""

from __future__ import annotations

import functools
import mimetypes
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/javascript", ".js")


class WasmRangeHandler(SimpleHTTPRequestHandler):
    """HTTP Range (206 Partial Content) ve COOP/COEP başlıklarını ekler."""

    def end_headers(self) -> None:
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self) -> None:
        range_hdr = self.headers.get("Range")
        if not range_hdr:
            super().do_GET()
            return

        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Dosya bulunamadı")
            return

        size = path.stat().st_size
        m = re.match(r"^bytes=(\d+)-(\d*)$", range_hdr.strip())
        if not m:
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Geçersiz Range")
            return

        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
        if start > end or end >= size:
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Aralık dosya dışında")
            return

        length = end - start + 1
        ctype = self.guess_type(str(path))
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def serve_directory(directory: Path, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Verilen dist/ dizinini COOP/COEP + Range destekli HTTP sunucusuyla sunar."""
    handler = functools.partial(WasmRangeHandler, directory=str(directory))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"ps1towasm sunucusu çalışıyor: http://{host}:{port} (dizin: {directory})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
