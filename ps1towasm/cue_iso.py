"""PS1 .cue ayrıştırıcı ve Mode 2 (2352 bayt/sektör) ISO9660 okuyucu."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SECTOR_SIZE = 2352
MODE2_USER_OFFSET = 24  # 12 sync + 4 header + 8 subheader
MODE2_USER_SIZE = 2048
PVD_SECTOR = 16


@dataclass(frozen=True)
class CueTrack:
    number: int
    mode: str
    index01_lba: int


@dataclass(frozen=True)
class DiscMetadata:
    bin_path: Path
    cue_path: Path | None
    total_bytes: int
    sector_count: int
    volume_id: str
    boot_exe: str | None
    tracks: list[CueTrack]


def msf_to_lba(msf: str) -> int:
    """MM:SS:FF zaman kodunu LBA sektör indeksine çevirir."""
    m, s, f = (int(part) for part in msf.split(":"))
    return (m * 60 + s) * 75 + f


def parse_cue(cue_path: Path) -> list[CueTrack]:
    """CUE dosyasından TRACK ve INDEX 01 kayıtlarını okur."""
    text = cue_path.read_text(encoding="utf-8", errors="replace")
    tracks: list[CueTrack] = []
    cur_num: int | None = None
    cur_mode = "MODE2/2352"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if m := re.match(r"^TRACK\s+(\d+)\s+(\S+)", line, re.IGNORECASE):
            cur_num = int(m.group(1))
            cur_mode = m.group(2).upper()
        elif cur_num is not None and (
            m := re.match(r"^INDEX\s+01\s+(\d+:\d+:\d+)", line, re.IGNORECASE)
        ):
            tracks.append(
                CueTrack(number=cur_num, mode=cur_mode, index01_lba=msf_to_lba(m.group(1)))
            )
            cur_num = None
    return tracks


def read_mode2_user_sector(bin_file, lba: int) -> bytes:
    """Verilen LBA'daki 2352 baytlık ham sektörden 2048 bayt kullanıcı verisi döner."""
    bin_file.seek(lba * SECTOR_SIZE + MODE2_USER_OFFSET)
    data = bin_file.read(MODE2_USER_SIZE)
    if len(data) < MODE2_USER_SIZE:
        raise ValueError(f"LBA {lba} eksik okundu ({len(data)} bayt)")
    return data


def _find_file_in_root(bin_file, root_lba: int, root_size: int, target_name: str) -> bytes | None:
    """ISO9660 kök dizininde hedef dosyayı (örn. SYSTEM.CNF) arar ve içeriğini döner."""
    sectors = (root_size + MODE2_USER_SIZE - 1) // MODE2_USER_SIZE
    dir_bytes = b"".join(read_mode2_user_sector(bin_file, root_lba + i) for i in range(sectors))
    pos = 0
    target_upper = target_name.upper()
    while pos < len(dir_bytes):
        rec_len = dir_bytes[pos]
        if rec_len == 0:
            # Sonraki sektör sınırına atla
            next_sec = ((pos // MODE2_USER_SIZE) + 1) * MODE2_USER_SIZE
            if next_sec >= len(dir_bytes):
                break
            pos = next_sec
            continue
        name_len = dir_bytes[pos + 32]
        raw_name = dir_bytes[pos + 33 : pos + 33 + name_len].decode("ascii", errors="ignore")
        clean_name = raw_name.split(";")[0].upper()
        if clean_name == target_upper:
            extent_lba = int.from_bytes(dir_bytes[pos + 2 : pos + 6], "little")
            data_len = int.from_bytes(dir_bytes[pos + 10 : pos + 14], "little")
            n_sec = (data_len + MODE2_USER_SIZE - 1) // MODE2_USER_SIZE
            content = b"".join(
                read_mode2_user_sector(bin_file, extent_lba + i) for i in range(n_sec)
            )
            return content[:data_len]
        pos += rec_len
    return None


def inspect_disc(bin_path: Path, cue_path: Path | None = None) -> DiscMetadata:
    """PS1 .bin/.cue imajını doğrular ve ISO9660 + SYSTEM.CNF meta verisini çıkarır."""
    total_bytes = bin_path.stat().st_size
    if total_bytes == 0 or total_bytes % SECTOR_SIZE != 0:
        raise ValueError(f"Geçersiz PS1 BIN boyutu: {total_bytes} bayt (2352 katı olmalı)")

    sector_count = total_bytes // SECTOR_SIZE
    tracks = (
        parse_cue(cue_path) if cue_path and cue_path.exists() else [CueTrack(1, "MODE2/2352", 0)]
    )

    with bin_path.open("rb") as f:
        pvd = read_mode2_user_sector(f, PVD_SECTOR)
        if pvd[0:6] != b"\x01CD001":
            raise ValueError("Sektör 16'da ISO9660 Primary Volume Descriptor (CD001) bulunamadı")
        volume_id = pvd[40:72].decode("ascii", errors="replace").strip()
        root_rec = pvd[156:190]
        root_lba = int.from_bytes(root_rec[2:6], "little")
        root_size = int.from_bytes(root_rec[10:14], "little")

        boot_exe: str | None = None
        sys_cnf = _find_file_in_root(f, root_lba, root_size, "SYSTEM.CNF")
        if sys_cnf:
            cnf_text = sys_cnf.decode("ascii", errors="replace")
            if m := re.search(r"BOOT\s*=\s*cdrom:\\*([^\s;]+)", cnf_text, re.IGNORECASE):
                boot_exe = m.group(1).strip()

    return DiscMetadata(
        bin_path=bin_path,
        cue_path=cue_path,
        total_bytes=total_bytes,
        sector_count=sector_count,
        volume_id=volume_id,
        boot_exe=boot_exe,
        tracks=tracks,
    )
