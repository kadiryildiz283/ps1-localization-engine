"""PS1 BIN/CUE imajını statik web (WASM) paketine dönüştüren derleyici/paketleyici."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from .cue_iso import SECTOR_SIZE, DiscMetadata, inspect_disc

WEB_TEMPLATE_DIR = Path(__file__).resolve().parent / "web"
DEFAULT_CHUNK_SECTORS = 890  # ~2.0 MiB (890 * 2352 = 2,093,280 bayt)


def _format_cue(tracks: list) -> str:
    """Nostalgist/RetroArch uyumlu normalize edilmiş disc.cue içeriği üretir."""
    lines = ['FILE "disc.bin" BINARY']
    for t in tracks:
        lba = t.index01_lba
        f = lba % 75
        total_sec = lba // 75
        s = total_sec % 60
        m = total_sec // 60
        lines.append(f"  TRACK {t.number:02d} {t.mode}")
        lines.append(f"    INDEX 01 {m:02d}:{s:02d}:{f:02d}")
    return "\n".join(lines) + "\n"


def _copy_web_assets(out_dir: Path) -> None:
    for asset in WEB_TEMPLATE_DIR.iterdir():
        if asset.is_file():
            shutil.copy2(asset, out_dir / asset.name)


def _write_chunks(bin_path: Path, out_dir: Path, chunk_sectors: int) -> list[dict]:
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_bytes = chunk_sectors * SECTOR_SIZE
    chunks_meta: list[dict] = []

    with bin_path.open("rb") as src:
        idx = 0
        while True:
            data = src.read(chunk_bytes)
            if not data:
                break
            rel_path = f"chunks/chunk_{idx:04d}.bin"
            (out_dir / rel_path).write_bytes(data)
            chunks_meta.append(
                {
                    "index": idx,
                    "path": rel_path,
                    "bytes": len(data),
                    "sectors": len(data) // SECTOR_SIZE,
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            idx += 1
    return chunks_meta


def build_web_bundle(
    bin_path: Path,
    out_dir: Path,
    cue_path: Path | None = None,
    mode: str = "chunked",
    chunk_sectors: int = DEFAULT_CHUNK_SECTORS,
    core_wasm: Path | None = None,
    bios_bin: Path | None = None,
) -> dict:
    """Final PS1 BIN/CUE imajından web'de çalışabilir statik dist/ paketi üretir."""
    if mode not in ("chunked", "range"):
        raise ValueError(f"Desteklenmeyen mod: {mode} ('chunked' veya 'range' olmalı)")
    if chunk_sectors <= 0:
        raise ValueError("chunk_sectors pozitif olmalı")

    meta: DiscMetadata = inspect_disc(bin_path, cue_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_web_assets(out_dir)

    core_rel: str | None = None
    if core_wasm is not None:
        core_dir = out_dir / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core_wasm, core_dir / core_wasm.name)
        core_rel = f"core/{core_wasm.name}"

    bios_rel: str | None = None
    if bios_bin is not None:
        core_dir = out_dir / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bios_bin, core_dir / bios_bin.name)
        bios_rel = f"core/{bios_bin.name}"

    (out_dir / "disc.cue").write_text(_format_cue(meta.tracks), encoding="utf-8")

    manifest: dict = {
        "schema_version": 1,
        "mode": mode,
        "volume_id": meta.volume_id,
        "boot_exe": meta.boot_exe,
        "sector_size": SECTOR_SIZE,
        "sector_count": meta.sector_count,
        "total_bytes": meta.total_bytes,
        "tracks": [asdict(t) for t in meta.tracks],
        "cue_url": "./disc.cue",
        "core_wasm": core_rel,
        "bios_bin": bios_rel,
    }

    if mode == "chunked":
        manifest["chunk_sectors"] = chunk_sectors
        manifest["chunks"] = _write_chunks(bin_path, out_dir, chunk_sectors)
    else:
        disc_name = "disc.bin"
        shutil.copy2(bin_path, out_dir / disc_name)
        manifest["disc_url"] = f"./{disc_name}"

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest
