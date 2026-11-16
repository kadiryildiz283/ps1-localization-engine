"""ps1towasm birim testleri (assetsiz sentetik Mode 2/2352 ISO9660 fixture ile)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from ps1towasm.cli import main as cli_main
from ps1towasm.compiler import build_web_bundle
from ps1towasm.cue_iso import MODE2_USER_OFFSET, PVD_SECTOR, SECTOR_SIZE, inspect_disc
from ps1towasm.server import WasmRangeHandler


def _make_mode2_sector(user_data: bytes) -> bytes:
    header = b"\x00" + b"\xff" * 10 + b"\x00" + b"\x00\x02\x00\x02" + b"\x00\x00\x08\x00" * 2
    padded = user_data.ljust(2048, b"\x00")[:2048]
    return (header + padded).ljust(SECTOR_SIZE, b"\x00")


def _build_synthetic_ps1_bin(tmp_dir: Path) -> tuple[Path, Path]:
    """Sektör 16'da PVD, 17'de root dir, 18'de SYSTEM.CNF içeren 20 sektörlük .bin/.cue üretir."""
    sectors = [bytearray(_make_mode2_sector(b"")) for _ in range(20)]

    # Sektör 16: ISO9660 Primary Volume Descriptor
    pvd = bytearray(2048)
    pvd[0:6] = b"\x01CD001"
    pvd[40:72] = b"HP_CHAMBER_TR".ljust(32, b" ")
    # Root directory record (offset 156, length 34)
    pvd[156] = 34
    pvd[158:162] = (17).to_bytes(4, "little")  # root LBA = 17
    pvd[166:170] = (2048).to_bytes(4, "little")  # root size = 2048
    sectors[PVD_SECTOR] = bytearray(_make_mode2_sector(bytes(pvd)))

    # Sektör 17: Root directory entry for SYSTEM.CNF;1 -> LBA 18
    cnf_bytes = b"BOOT = cdrom:\\SLES_039.72;1\r\nTCB = 4\r\n"
    name = b"SYSTEM.CNF;1"
    rec_len = 33 + len(name) + (1 if (33 + len(name)) % 2 else 0)
    root_dir = bytearray(2048)
    root_dir[0] = rec_len
    root_dir[2:6] = (18).to_bytes(4, "little")
    root_dir[10:14] = len(cnf_bytes).to_bytes(4, "little")
    root_dir[32] = len(name)
    root_dir[33 : 33 + len(name)] = name
    sectors[17] = bytearray(_make_mode2_sector(bytes(root_dir)))

    # Sektör 18: SYSTEM.CNF
    sectors[18] = bytearray(_make_mode2_sector(cnf_bytes))

    bin_path = tmp_dir / "test_game.bin"
    bin_path.write_bytes(b"".join(sectors))
    cue_path = tmp_dir / "test_game.cue"
    cue_path.write_text(
        'FILE "test_game.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n',
        encoding="utf-8",
    )
    return bin_path, cue_path


class Ps1ToWasmTests(unittest.TestCase):
    def test_inspect_disc_reads_pvd_and_boot_exe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bin_path, cue_path = _build_synthetic_ps1_bin(Path(td))
            meta = inspect_disc(bin_path, cue_path)
            self.assertEqual(meta.sector_count, 20)
            self.assertEqual(meta.total_bytes, 20 * SECTOR_SIZE)
            self.assertEqual(meta.volume_id, "HP_CHAMBER_TR")
            self.assertEqual(meta.boot_exe, "SLES_039.72")
            self.assertEqual(len(meta.tracks), 1)
            self.assertEqual(meta.tracks[0].mode, "MODE2/2352")

    def test_build_chunked_preserves_exact_bytes_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_path, cue_path = _build_synthetic_ps1_bin(root)
            out_dir = root / "dist"
            manifest = build_web_bundle(
                bin_path, out_dir, cue_path=cue_path, mode="chunked", chunk_sectors=7
            )

            self.assertEqual(manifest["mode"], "chunked")
            self.assertEqual(len(manifest["chunks"]), 3)  # 7 + 7 + 6 = 20 sektör
            reassembled = b"".join((out_dir / c["path"]).read_bytes() for c in manifest["chunks"])
            self.assertEqual(reassembled, bin_path.read_bytes())
            for c in manifest["chunks"]:
                digest = hashlib.sha256((out_dir / c["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, c["sha256"])

            self.assertEqual(manifest["cue_url"], "./disc.cue")
            self.assertTrue((out_dir / "disc.cue").is_file())
            self.assertIn(
                'FILE "disc.bin" BINARY', (out_dir / "disc.cue").read_text(encoding="utf-8")
            )
            self.assertTrue((out_dir / "index.html").is_file())
            self.assertTrue((out_dir / "range-cdrom.js").is_file())
            self.assertTrue((out_dir / "coi-serviceworker.js").is_file())

    def test_cli_inspect_and_range_server(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_path, cue_path = _build_synthetic_ps1_bin(root)
            out_dir = root / "dist_range"
            rc = cli_main(
                [
                    "build",
                    "--bin",
                    str(bin_path),
                    "--cue",
                    str(cue_path),
                    "--out",
                    str(out_dir),
                    "--mode",
                    "range",
                ]
            )
            self.assertEqual(rc, 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["disc_url"], "./disc.bin")

            handler = partial(WasmRangeHandler, directory=str(out_dir))
            srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                start = PVD_SECTOR * SECTOR_SIZE + MODE2_USER_OFFSET
                end = start + 5
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/disc.bin",
                    headers={"Range": f"bytes={start}-{end}"},
                )
                with urllib.request.urlopen(req) as resp:
                    self.assertEqual(resp.status, 206)
                    self.assertEqual(resp.headers.get("Cross-Origin-Opener-Policy"), "same-origin")
                    self.assertEqual(
                        resp.headers.get("Cross-Origin-Embedder-Policy"), "require-corp"
                    )
                    self.assertEqual(resp.read(), b"\x01CD001")
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
