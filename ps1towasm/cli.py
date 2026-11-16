"""ps1towasm CLI: inspect / build / serve."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .compiler import DEFAULT_CHUNK_SECTORS, build_web_bundle
from .cue_iso import inspect_disc
from .server import serve_directory


def _cmd_inspect(args: argparse.Namespace) -> int:
    meta = inspect_disc(Path(args.bin), Path(args.cue) if args.cue else None)
    payload = {
        "bin_path": str(meta.bin_path),
        "cue_path": str(meta.cue_path) if meta.cue_path else None,
        "total_bytes": meta.total_bytes,
        "sector_count": meta.sector_count,
        "volume_id": meta.volume_id,
        "boot_exe": meta.boot_exe,
        "tracks": [asdict(t) for t in meta.tracks],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    manifest = build_web_bundle(
        bin_path=Path(args.bin),
        out_dir=Path(args.out),
        cue_path=Path(args.cue) if args.cue else None,
        mode=args.mode,
        chunk_sectors=args.chunk_sectors,
        core_wasm=Path(args.core) if args.core else None,
        bios_bin=Path(args.bios) if args.bios else None,
    )
    summary = {
        "out": args.out,
        "mode": manifest["mode"],
        "volume_id": manifest["volume_id"],
        "boot_exe": manifest["boot_exe"],
        "sector_count": manifest["sector_count"],
        "chunks": len(manifest.get("chunks", [])),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    serve_directory(Path(args.dir), host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ps1towasm", description="PS1 BIN/CUE → Web (WASM) paketleyici"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser(
        "inspect", help="BIN/CUE meta verisini ve SYSTEM.CNF bilgisini doğrula"
    )
    p_inspect.add_argument("--bin", required=True, help="PS1 .bin disk imajı")
    p_inspect.add_argument("--cue", help="İsteğe bağlı .cue dosyası")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_build = sub.add_parser("build", help="Web'de çalışabilir statik dist/ paketi üret")
    p_build.add_argument("--bin", required=True, help="PS1 .bin disk imajı")
    p_build.add_argument("--cue", help="İsteğe bağlı .cue dosyası")
    p_build.add_argument(
        "--out", default="ps1towasm/dist", help="Çıktı dizini (varsayılan: ps1towasm/dist)"
    )
    p_build.add_argument(
        "--mode", choices=["chunked", "range"], default="chunked", help="Disk akış modu"
    )
    p_build.add_argument(
        "--chunk-sectors", type=int, default=DEFAULT_CHUNK_SECTORS, help="Parça başına sektör"
    )
    p_build.add_argument("--core", help="WASM PS1 çekirdek dosyası (.wasm)")
    p_build.add_argument("--bios", help="Açık kaynak BIOS dosyası (örn. openbios.bin)")
    p_build.set_defaults(func=_cmd_build)

    p_serve = sub.add_parser("serve", help="Üretilen dist/ dizinini COOP/COEP + Range ile sun")
    p_serve.add_argument("dir", nargs="?", default="ps1towasm/dist", help="Sunulacak dizin")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
