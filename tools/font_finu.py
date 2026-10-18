"""Turkish Font Patch Generator for Argonaut PS1 UNIF/FINU Chunk.

Injects custom 1bpp monochrome bitmaps for Turkish characters:
- ı (dotless i) -> slot 0xA0
- İ (dotted capital I) -> slot 0x8D
- ş (lowercase s with cedilla) -> slot 0xB0
- Ş (uppercase S with cedilla) -> slot 0x95
- ğ (lowercase g with breve) -> slot 0x9D
- Ğ (uppercase G with breve) -> slot 0x8A
"""

import struct

def generate_turkish_finu(orig_finu_bytes: bytes) -> bytes:
    finu = bytearray(orig_finu_bytes)
    assert len(finu) == 10240, f'Expected 10240 bytes, got {len(finu)}'

    def get_glyph_rows(off, width):
        stride = (width + 7) // 8
        base = 1736 + off
        rows = []
        for r in range(16):
            b = finu[base + r * stride : base + (r + 1) * stride]
            rows.append(bytearray(b))
        return rows

    def write_glyph(idx, unicode_code, width, rows):
        entry_pos = 16 + idx * 8
        old_w, old_u, off = struct.unpack('<HHI', finu[entry_pos:entry_pos+8])
        stride = (width + 7) // 8
        struct.pack_into('<HHI', finu, entry_pos, width, unicode_code, off)
        
        base = 1736 + off
        for r in range(16):
            row_bytes = bytes(rows[r])
            if len(row_bytes) < stride:
                row_bytes = row_bytes.ljust(stride, b'\x00')
            finu[base + r * stride : base + r * stride + len(row_bytes)] = row_bytes

    # 1. 'ı' from 'i' (off=0x09D0, w=5) -> Slot 0xA0
    rows_i = get_glyph_rows(0x09D0, 5)
    rows_dotless_i = [bytearray(r) for r in rows_i]
    rows_dotless_i[3] = bytearray([0x00])
    rows_dotless_i[4] = bytearray([0x00])
    write_glyph(0xA0, 0x0131, 5, rows_dotless_i)

    # 2. 'İ' from 'I' (off=0x0660, w=7) -> Slot 0x8D
    rows_I = get_glyph_rows(0x0660, 7)
    rows_dot_I = [bytearray(r) for r in rows_I]
    rows_dot_I[0] = bytearray([0x18])
    rows_dot_I[1] = bytearray([0x18])
    write_glyph(0x8D, 0x0130, 7, rows_dot_I)

    # 3. 'ş' from 's' (off=0x0AD0, w=7) -> Slot 0xB0
    rows_s = get_glyph_rows(0x0AD0, 7)
    rows_sh = [bytearray(r) for r in rows_s]
    rows_sh[13] = bytearray([0x18])
    rows_sh[14] = bytearray([0x30])
    write_glyph(0xB0, 0x015F, 7, rows_sh)

    # 4. 'Ş' from 'S' (off=0x07A0, w=10) -> Slot 0x95
    rows_S = get_glyph_rows(0x07A0, 10)
    rows_SH = [bytearray(r) for r in rows_S]
    rows_SH[13] = bytearray([0x08, 0x00])
    rows_SH[14] = bytearray([0x18, 0x00])
    write_glyph(0x95, 0x015E, 10, rows_SH)

    # 5. 'ğ' from 'g' (off=0x0990, w=9) -> Slot 0x9D
    rows_g = get_glyph_rows(0x0990, 9)
    rows_gh = [bytearray(r) for r in rows_g]
    rows_gh[3] = bytearray([0x44, 0x00])
    rows_gh[4] = bytearray([0x38, 0x00])
    write_glyph(0x9D, 0x011F, 9, rows_gh)

    # 6. 'Ğ' from 'G' (off=0x0620, w=13) -> Slot 0x8A
    rows_G = get_glyph_rows(0x0620, 13)
    rows_GH = [bytearray(r) for r in rows_G]
    rows_GH[0] = bytearray([0x42, 0x00])
    rows_GH[1] = bytearray([0x3C, 0x00])
    write_glyph(0x8A, 0x011E, 13, rows_GH)

    return bytes(finu)
